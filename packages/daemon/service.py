"""Multi-Worktree Daemon coordinator for Causa."""

import threading
import time
from typing import Dict, Any, List, Optional
from packages.fullerence.storage import FullerenceStorage
from packages.daemon.watcher import WorktreeWatcher
from packages.daemon.sync import BlackboardSynchronizer


class MultiWorktreeDaemon:
    """Daemon service coordinating dynamic worktree watching and live blackboard sync."""

    def __init__(self, worktrees_dir: str, storage: FullerenceStorage) -> None:
        self.worktrees_dir = worktrees_dir
        self.storage = storage
        self.watcher = WorktreeWatcher(worktrees_dir)
        self.synchronizer = BlackboardSynchronizer(storage)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def poll_once(self) -> Dict[str, Any]:
        """Performs a single cycle of dynamic discovery and AST synchronization."""
        # 1. Discover newly created or removed worktrees
        active = self.watcher.discover_worktrees()

        # 2. Scan for file changes across all active worktrees
        changes = self.watcher.scan_for_file_changes()

        synced_entries: List[str] = []

        # 3. Synchronize AST interface changes to shared blackboard
        for wt_path, files in changes.items():
            for rel_file in files:
                entries = self.synchronizer.sync_file_to_blackboard(wt_path, rel_file)
                for e in entries:
                    synced_entries.append(f"{e.symbol_id} in {wt_path}")

        return {
            "active_worktrees_count": len(active),
            "active_worktrees": active,
            "modified_files_count": sum(len(f) for f in changes.values()),
            "synced_symbols_count": len(synced_entries),
            "synced_symbols": synced_entries,
        }

    def start_background(self, interval_seconds: float = 0.5) -> None:
        """Starts the daemon loop in a background daemon thread."""
        if self._running:
            return

        self._running = True

        def _loop():
            while self._running:
                try:
                    self.poll_once()
                except Exception:
                    pass
                time.sleep(interval_seconds)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the background daemon worker."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
