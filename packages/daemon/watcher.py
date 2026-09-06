"""Dynamic multi-worktree filesystem watcher for Causa."""

import os
import time
from typing import Dict, Set, List, Callable, Optional


class WorktreeWatcher:
    """Discovers and monitors active Git worktrees under .causa/worktrees/."""

    def __init__(self, worktrees_dir: str) -> None:
        self.worktrees_dir = os.path.abspath(worktrees_dir)
        self.active_worktrees: Set[str] = set()
        # Mapping: worktree_path -> { relative_file_path: mtime }
        self.file_snapshots: Dict[str, Dict[str, float]] = {}
        # Callbacks
        self.on_worktree_created: Optional[Callable[[str], None]] = None
        self.on_worktree_deleted: Optional[Callable[[str], None]] = None
        self.on_file_changed: Optional[Callable[[str, str], None]] = None

    def discover_worktrees(self) -> List[str]:
        """Scans the worktrees root directory for active agent subdirectories."""
        if not os.path.exists(self.worktrees_dir):
            return []

        current_dirs: Set[str] = set()
        for entry in os.listdir(self.worktrees_dir):
            full_path = os.path.join(self.worktrees_dir, entry)
            if os.path.isdir(full_path):
                current_dirs.add(full_path)

        # 1. Detect newly created worktrees
        new_worktrees = current_dirs - self.active_worktrees
        for wt in new_worktrees:
            self.register_worktree(wt)
            if self.on_worktree_created:
                self.on_worktree_created(wt)

        # 2. Detect deleted/torn down worktrees
        deleted_worktrees = self.active_worktrees - current_dirs
        for wt in deleted_worktrees:
            self.unregister_worktree(wt)
            if self.on_worktree_deleted:
                self.on_worktree_deleted(wt)

        return sorted(list(self.active_worktrees))

    def register_worktree(self, worktree_path: str) -> None:
        """Registers a new worktree directory and takes an initial snapshot of its files."""
        normalized = os.path.abspath(worktree_path)
        self.active_worktrees.add(normalized)
        self.file_snapshots[normalized] = self._snapshot_files(normalized)

    def unregister_worktree(self, worktree_path: str) -> None:
        """Unregisters a worktree directory and purges its file tracking state."""
        normalized = os.path.abspath(worktree_path)
        self.active_worktrees.discard(normalized)
        self.file_snapshots.pop(normalized, None)

    def scan_for_file_changes(self) -> Dict[str, List[str]]:
        """
        Scans all active worktrees for modified or new files since the last snapshot.
        Returns a mapping of worktree_path -> list of modified relative file paths.
        """
        changed_by_worktree: Dict[str, List[str]] = {}

        for wt in list(self.active_worktrees):
            if not os.path.exists(wt):
                continue

            previous_snapshot = self.file_snapshots.get(wt, {})
            current_snapshot = self._snapshot_files(wt)
            modified_files: List[str] = []

            for rel_path, mtime in current_snapshot.items():
                prev_mtime = previous_snapshot.get(rel_path)
                if prev_mtime is None or mtime > prev_mtime:
                    modified_files.append(rel_path)
                    if self.on_file_changed:
                        self.on_file_changed(wt, rel_path)

            if modified_files:
                changed_by_worktree[wt] = modified_files

            self.file_snapshots[wt] = current_snapshot

        return changed_by_worktree

    def _snapshot_files(self, directory: str) -> Dict[str, float]:
        """Takes a snapshot of all file modification times in a worktree."""
        snapshot: Dict[str, float] = {}
        if not os.path.exists(directory):
            return snapshot

        for root, dirs, files in os.walk(directory):
            # Ignore .git and cache folders
            dirs[:] = [d for d in dirs if not d.startswith(".git") and d != "__pycache__" and d != ".pytest_cache"]
            for file in files:
                if file.endswith((".py", ".ts", ".js", ".json", ".md")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, directory).replace("\\", "/")
                    try:
                        snapshot[rel_path] = os.path.getmtime(full_path)
                    except OSError:
                        pass
        return snapshot
