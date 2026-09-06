"""Multi-worktree dynamic file watcher and shared blackboard synchronization."""

import ast
import os
import threading
import time
from typing import Dict, Any, List, Set, Optional, Callable
from packages.fullerence.types import BlackboardEntry
from packages.fullerence.storage import FullerenceStorage


class WorktreeWatcher:
    """Discovers and monitors active Git worktrees under .causa/worktrees/."""

    def __init__(self, worktrees_dir: str) -> None:
        self.worktrees_dir = os.path.abspath(worktrees_dir)
        self.active_worktrees: Set[str] = set()
        self.file_snapshots: Dict[str, Dict[str, float]] = {}
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
        """Scans all active worktrees for modified or new files since the last snapshot."""
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


class BlackboardSynchronizer:
    """Extracts exported symbol signatures and updates the shared SQLite blackboard."""

    def __init__(self, storage: FullerenceStorage) -> None:
        self.storage = storage

    def sync_file_to_blackboard(
        self,
        worktree_path: str,
        relative_file_path: str,
        agent_id: Optional[str] = None,
    ) -> List[BlackboardEntry]:
        """Parses an updated source file in a worktree and synchronizes exported symbols to SQLite."""
        full_path = os.path.join(worktree_path, relative_file_path)
        if not os.path.exists(full_path):
            return []

        if not agent_id:
            agent_id = os.path.basename(os.path.normpath(worktree_path))

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return []

        entries: List[BlackboardEntry] = []

        if relative_file_path.endswith(".py"):
            entries = self._extract_python_symbols(source, relative_file_path, agent_id)
        else:
            entries = self._extract_generic_symbols(source, relative_file_path, agent_id)

        for entry in entries:
            self.storage.update_blackboard(entry)

        return entries

    def _extract_python_symbols(
        self, source: str, file_path: str, agent_id: str
    ) -> List[BlackboardEntry]:
        """Extracts top-level functions and classes using Python's AST parser."""
        entries: List[BlackboardEntry] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        now = int(time.time() * 1000)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                args_str = self._format_arguments(node.args)
                ret_annotation = self._unparse_node(node.returns) if node.returns else "None"
                signature = f"{node.name}({args_str}) -> {ret_annotation}"

                entry = BlackboardEntry(
                    id=f"bb_{agent_id}_{node.name}",
                    symbol_id=f"func_{node.name}",
                    name=node.name,
                    signature=signature,
                    file_path=file_path,
                    agent_id=agent_id,
                    updated_at=now,
                )
                entries.append(entry)

            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue

                signature = f"class {node.name}"
                entry = BlackboardEntry(
                    id=f"bb_{agent_id}_{node.name}",
                    symbol_id=f"class_{node.name}",
                    name=node.name,
                    signature=signature,
                    file_path=file_path,
                    agent_id=agent_id,
                    updated_at=now,
                )
                entries.append(entry)

        return entries

    def _extract_generic_symbols(
        self, source: str, file_path: str, agent_id: str
    ) -> List[BlackboardEntry]:
        """Fallback lightweight symbol extractor for non-python files."""
        entries: List[BlackboardEntry] = []
        now = int(time.time() * 1000)
        for line in source.splitlines():
            line = line.strip()
            if line.startswith("export function ") or line.startswith("function "):
                parts = line.split("(", 1)
                name = parts[0].replace("export function ", "").replace("function ", "").strip()
                signature = line.replace("export ", "").rstrip("{").strip()
                entries.append(
                    BlackboardEntry(
                        id=f"bb_{agent_id}_{name}",
                        symbol_id=f"func_{name}",
                        name=name,
                        signature=signature,
                        file_path=file_path,
                        agent_id=agent_id,
                        updated_at=now,
                    )
                )
        return entries

    def _format_arguments(self, args: ast.arguments) -> str:
        """Formats an ast.arguments node into a readable parameter string."""
        formatted: List[str] = []
        for arg in args.args:
            arg_name = arg.arg
            if arg.annotation:
                ann = self._unparse_node(arg.annotation)
                formatted.append(f"{arg_name}: {ann}")
            else:
                formatted.append(arg_name)
        return ", ".join(formatted)

    def _unparse_node(self, node: ast.AST) -> str:
        """Helper to convert AST expression nodes to string representation."""
        try:
            return ast.unparse(node)
        except Exception:
            return "Any"


class WorktreeDaemon:
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
        active = self.watcher.discover_worktrees()
        changes = self.watcher.scan_for_file_changes()
        synced_entries: List[str] = []

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


# Alias
MultiWorktreeDaemon = WorktreeDaemon

__all__ = [
    "WorktreeWatcher",
    "BlackboardSynchronizer",
    "WorktreeDaemon",
    "MultiWorktreeDaemon",
]
