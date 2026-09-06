"""Shared Blackboard synchronizer extracting AST interfaces across worktrees."""

import ast
import os
import time
from typing import Dict, Any, List, Optional
from packages.core.schemas.nodes import BlackboardEntry
from packages.fullerence.storage import FullerenceStorage


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
            # Fallback text signature extractor
            entries = self._extract_generic_symbols(source, relative_file_path, agent_id)

        # Upsert extracted entries into SQLite blackboard
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
                # Ignore internal/private helper functions starting with '_'
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
