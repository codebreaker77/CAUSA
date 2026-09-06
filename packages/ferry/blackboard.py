"""Ferry Shared Interface Blackboard.

Provides a low-latency shared blackboard for broadcasting and discovering
exported AST contracts, signatures, and interface changes across agents.

Key capabilities:
1. Interface Publishing: Automatically publishes updated symbol signatures
   when agents successfully commit file mutations.
2. Interface Discovery: Subagents can query the current public contract of any
   dependency without ingesting thousands of tokens of entire source files.
3. Historical Timeline: Tracks contract changes per symbol with agent attribution.
4. Fullerence Substrate Sync: Seamlessly syncs entries with SQLite WAL storage.
"""

import time
import uuid
import threading
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

try:
    from packages.fullerence.types import BlackboardEntry
except Exception:
    class BlackboardEntry(BaseModel):
        id: str
        symbol_id: str
        name: str
        signature: str
        file_path: str
        agent_id: str
        updated_at: int = Field(default_factory=lambda: int(time.time()))


class Blackboard:
    """In-memory low-latency blackboard for AST interface contracts,
    backed by optional persistence in Fullerence storage.
    """

    def __init__(self, storage: Optional[Any] = None) -> None:
        self.storage = storage
        self._lock = threading.RLock()
        
        # symbol_id -> BlackboardEntry
        self._entries: Dict[str, BlackboardEntry] = {}
        
        # symbol_id -> List[BlackboardEntry] (chronological revisions)
        self._history: Dict[str, List[BlackboardEntry]] = {}

    # -------------------------------------------------------------
    # 1. Publish / Update Contract
    # -------------------------------------------------------------
    def publish(
        self,
        symbol_id: str,
        name: str,
        signature: str,
        file_path: str,
        agent_id: str,
        entry_id: Optional[str] = None,
    ) -> BlackboardEntry:
        """Publishes or updates an exported symbol's contract signature on the blackboard."""
        now = int(time.time())
        norm_path = file_path.replace("\\", "/").strip().lower()
        eid = entry_id or f"bb_{uuid.uuid4().hex[:10]}"

        entry = BlackboardEntry(
            id=eid,
            symbol_id=symbol_id,
            name=name,
            signature=signature,
            file_path=norm_path,
            agent_id=agent_id,
            updated_at=now,
        )

        with self._lock:
            self._entries[symbol_id] = entry
            if symbol_id not in self._history:
                self._history[symbol_id] = []
            self._history[symbol_id].append(entry)

        # Persist to Fullerence storage if wired
        if self.storage and hasattr(self.storage, "update_blackboard"):
            try:
                self.storage.update_blackboard(entry)
            except Exception:
                pass

        return entry

    # -------------------------------------------------------------
    # 2. Bulk Publish from AST Diffs / Symbols
    # -------------------------------------------------------------
    def publish_symbols(
        self,
        symbols_dict: Dict[str, Any],
        file_path: str,
        agent_id: str,
    ) -> List[BlackboardEntry]:
        """Convenience method to publish a dictionary of SymbolSignature objects."""
        published: List[BlackboardEntry] = []
        for sym_id, sym in symbols_dict.items():
            entry = self.publish(
                symbol_id=sym_id,
                name=sym.name,
                signature=sym.signature,
                file_path=file_path,
                agent_id=agent_id,
            )
            published.append(entry)
        return published

    # -------------------------------------------------------------
    # 3. Query Active Contracts
    # -------------------------------------------------------------
    def get_symbol(self, symbol_id: str) -> Optional[BlackboardEntry]:
        """Gets the latest contract for a specific symbol."""
        with self._lock:
            return self._entries.get(symbol_id)

    def get_file_contracts(self, file_path: str) -> List[BlackboardEntry]:
        """Returns all currently active symbol signatures defined in a file."""
        norm_path = file_path.replace("\\", "/").strip().lower()
        with self._lock:
            return [
                entry for entry in self._entries.values()
                if entry.file_path == norm_path
            ]

    def get_all_contracts(self) -> List[BlackboardEntry]:
        """Returns all currently active symbol signatures across the entire project."""
        with self._lock:
            return list(self._entries.values())

    def get_symbol_history(self, symbol_id: str) -> List[BlackboardEntry]:
        """Returns the chronological revision history of a symbol's contract."""
        with self._lock:
            return list(self._history.get(symbol_id, []))

    # -------------------------------------------------------------
    # 4. Invalidate / Remove Symbols (e.g. on Rollback or Deletion)
    # -------------------------------------------------------------
    def remove_symbol(self, symbol_id: str) -> bool:
        """Removes a symbol from the active blackboard (e.g. if deleted)."""
        with self._lock:
            if symbol_id in self._entries:
                del self._entries[symbol_id]
                return True
            return False

    def clear(self) -> None:
        """Clears all blackboard entries (useful for session resets)."""
        with self._lock:
            self._entries.clear()
            self._history.clear()
