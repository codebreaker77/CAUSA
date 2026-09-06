"""Ferry Lock & Lease Manager.

Provides deterministic multi-agent concurrency protection through file leases.
Eliminates race conditions and dirty writes across concurrent agents with:
- Exclusive WRITE leases and shared READ leases.
- Heartbeat renewal and automatic TTL expiration to prevent deadlocks from crashed agents.
- Conflict detection and queueing/rejection semantics.
- Direct persistence and auditing via FullerenceStorage when available.
"""

import time
import uuid
import threading
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
from pydantic import BaseModel, Field

# Direct import of types without triggering packages.fullerence.__init__ (which loads sqlalchemy)
try:
    from packages.fullerence.types import Lease, LeaseLockState
except Exception:
    class LeaseLockState(str, Enum):
        ACQUIRED = "acquired"
        RELEASED = "released"
        BLOCKED = "blocked"

    class Lease(BaseModel):
        id: str
        agent_id: str
        file_path: str
        lock_state: LeaseLockState = LeaseLockState.ACQUIRED
        timestamp: int = Field(default_factory=lambda: int(time.time()))


class LeaseLockType(str):
    EXCLUSIVE_WRITE = "WRITE"
    SHARED_READ = "READ"


class LockManager:
    """Coordinates read/write file leases across heterogeneous agents.
    
    Ensures safe concurrent access to codebase paths, backed by in-memory
    concurrency guards and optionally persisted into Fullerence SQLite storage.
    """

    def __init__(
        self,
        storage: Optional[Any] = None,
        default_ttl_seconds: int = 30,
    ) -> None:
        self.storage = storage
        self.default_ttl = default_ttl_seconds
        self._lock = threading.RLock()
        
        # In-memory tracking of active leases:
        # file_path -> {
        #    "lease_id": str,
        #    "agent_id": str,
        #    "lock_type": str (WRITE | READ),
        #    "readers": Set[str],
        #    "acquired_at": int (seconds),
        #    "expires_at": int (seconds),
        # }
        self._active_leases: Dict[str, dict] = {}

    # -------------------------------------------------------------
    # 1. Acquire Lease
    # -------------------------------------------------------------
    def acquire(
        self,
        agent_id: str,
        file_path: str,
        lock_type: str = LeaseLockType.EXCLUSIVE_WRITE,
        ttl_seconds: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[Lease]]:
        """Attempts to acquire a lease on a file path.
        
        Returns:
            Tuple of:
            - success: bool
            - reason: Optional[str] explaining failure if blocked
            - lease: Optional[Lease] object if acquired
        """
        norm_path = self._normalize_path(file_path)
        ttl = ttl_seconds or self.default_ttl
        now = int(time.time())

        with self._lock:
            # Clean up any expired leases first
            self._prune_expired_leases(now)

            current = self._active_leases.get(norm_path)

            # Case A: Path is currently held by someone
            if current:
                holding_agent = current["agent_id"]
                current_type = current["lock_type"]

                # If same agent already holds the lock, renew/re-enter it
                if holding_agent == agent_id:
                    current["expires_at"] = now + ttl
                    lease = self._create_and_persist_lease(
                        agent_id=agent_id,
                        file_path=norm_path,
                        lock_state=LeaseLockState.ACQUIRED,
                        now=now,
                        lease_id=current["lease_id"],
                    )
                    return True, None, lease

                # If requesting SHARED_READ and currently held lock is also SHARED_READ
                if lock_type == LeaseLockType.SHARED_READ and current_type == LeaseLockType.SHARED_READ:
                    current["readers"].add(agent_id)
                    current["expires_at"] = max(current["expires_at"], now + ttl)
                    lease = self._create_and_persist_lease(
                        agent_id=agent_id,
                        file_path=norm_path,
                        lock_state=LeaseLockState.ACQUIRED,
                        now=now,
                    )
                    return True, None, lease

                # Conflict: Either current is EXCLUSIVE_WRITE, or incoming is EXCLUSIVE_WRITE
                remaining_time = max(0, current["expires_at"] - now)
                conflict_reason = (
                    f"Conflict on '{norm_path}': currently locked by agent '{holding_agent}' "
                    f"({current_type} lock). Expires in {remaining_time}s."
                )
                self._create_and_persist_lease(
                    agent_id=agent_id,
                    file_path=norm_path,
                    lock_state=LeaseLockState.BLOCKED,
                    now=now,
                )
                return False, conflict_reason, None

            # Case B: Path is free to acquire
            lease_id = f"lease_{uuid.uuid4().hex[:10]}"
            self._active_leases[norm_path] = {
                "lease_id": lease_id,
                "agent_id": agent_id,
                "lock_type": lock_type,
                "readers": {agent_id} if lock_type == LeaseLockType.SHARED_READ else set(),
                "acquired_at": now,
                "expires_at": now + ttl,
            }

            lease = self._create_and_persist_lease(
                agent_id=agent_id,
                file_path=norm_path,
                lock_state=LeaseLockState.ACQUIRED,
                now=now,
                lease_id=lease_id,
            )
            return True, None, lease

    # -------------------------------------------------------------
    # 2. Release Lease
    # -------------------------------------------------------------
    def release(self, agent_id: str, file_path: str) -> bool:
        """Explicitly releases a held lease by an agent."""
        norm_path = self._normalize_path(file_path)
        now = int(time.time())

        with self._lock:
            current = self._active_leases.get(norm_path)
            if not current:
                return False

            if current["lock_type"] == LeaseLockType.SHARED_READ:
                if agent_id in current["readers"]:
                    current["readers"].remove(agent_id)
                    if not current["readers"]:
                        del self._active_leases[norm_path]
            elif current["agent_id"] == agent_id:
                del self._active_leases[norm_path]
            else:
                return False

            self._create_and_persist_lease(
                agent_id=agent_id,
                file_path=norm_path,
                lock_state=LeaseLockState.RELEASED,
                now=now,
            )
            return True

    # -------------------------------------------------------------
    # 3. Heartbeat / Renew Lease
    # -------------------------------------------------------------
    def heartbeat(self, agent_id: str, file_path: str, extend_seconds: Optional[int] = None) -> bool:
        """Extends TTL of an active lease held by the agent."""
        norm_path = self._normalize_path(file_path)
        extend = extend_seconds or self.default_ttl
        now = int(time.time())

        with self._lock:
            current = self._active_leases.get(norm_path)
            if not current:
                return False

            if current["agent_id"] == agent_id or (
                current["lock_type"] == LeaseLockType.SHARED_READ and agent_id in current["readers"]
            ):
                current["expires_at"] = now + extend
                return True

            return False

    # -------------------------------------------------------------
    # 4. Query Active Leases & Status
    # -------------------------------------------------------------
    def get_lease(self, file_path: str) -> Optional[dict]:
        """Returns details about the active lease on a file path, if any."""
        norm_path = self._normalize_path(file_path)
        now = int(time.time())

        with self._lock:
            self._prune_expired_leases(now)
            current = self._active_leases.get(norm_path)
            if current:
                return {
                    "file_path": norm_path,
                    "agent_id": current["agent_id"],
                    "lock_type": current["lock_type"],
                    "expires_in_seconds": max(0, current["expires_at"] - now),
                    "readers": list(current["readers"]),
                }
            return None

    def list_active_leases(self) -> List[dict]:
        """Lists all currently active leases across all files."""
        now = int(time.time())
        with self._lock:
            self._prune_expired_leases(now)
            return [
                {
                    "file_path": path,
                    "agent_id": data["agent_id"],
                    "lock_type": data["lock_type"],
                    "expires_in_seconds": max(0, data["expires_at"] - now),
                    "readers": list(data["readers"]),
                }
                for path, data in self._active_leases.items()
            ]

    def release_all_for_agent(self, agent_id: str) -> int:
        """Releases all locks held by a specific agent (e.g. on agent termination/crash)."""
        now = int(time.time())
        released_count = 0

        with self._lock:
            paths_to_release = []
            for path, data in self._active_leases.items():
                if data["agent_id"] == agent_id or agent_id in data["readers"]:
                    paths_to_release.append(path)

            for path in paths_to_release:
                if self.release(agent_id, path):
                    released_count += 1

        return released_count

    # -------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------
    def _normalize_path(self, path: str) -> str:
        """Normalizes path separators and trims whitespace."""
        return path.replace("\\", "/").strip().lower()

    def _prune_expired_leases(self, now: int) -> None:
        """Removes leases whose TTL has expired."""
        expired = [path for path, data in self._active_leases.items() if data["expires_at"] <= now]
        for path in expired:
            data = self._active_leases.pop(path)
            if self.storage and hasattr(self.storage, "record_lease"):
                try:
                    self._create_and_persist_lease(
                        agent_id=data["agent_id"],
                        file_path=path,
                        lock_state=LeaseLockState.RELEASED,
                        now=now,
                    )
                except Exception:
                    pass

    def _create_and_persist_lease(
        self,
        agent_id: str,
        file_path: str,
        lock_state: LeaseLockState,
        now: int,
        lease_id: Optional[str] = None,
    ) -> Lease:
        """Creates a Lease object and records it in Fullerence storage if available."""
        lease = Lease(
            id=lease_id or f"lease_{uuid.uuid4().hex[:10]}",
            agent_id=agent_id,
            file_path=file_path,
            lock_state=lock_state,
            timestamp=now,
        )
        if self.storage and hasattr(self.storage, "record_lease"):
            try:
                self.storage.record_lease(lease)
            except Exception:
                pass
        return lease
