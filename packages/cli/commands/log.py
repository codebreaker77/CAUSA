"""Command: fullerenes log [sessionId] - renders the visual causal execution tree."""

from typing import Optional, List
from packages.fullerence.storage import FullerenceStorage
from packages.core.schemas.nodes import CausalNode


def format_causal_tree(nodes: List[CausalNode]) -> str:
    """Formats a list of causal execution nodes into a human-readable visual ASCII tree."""
    if not nodes:
        return "No causal execution nodes recorded for this session."

    lines: List[str] = []
    lines.append("\n=== CAUSAL EXECUTION GRAPH ===")

    # Sort nodes by creation time
    sorted_nodes = sorted(nodes, key=lambda n: n.created_at)

    for i, node in enumerate(sorted_nodes):
        prefix = "+-- " if i < len(sorted_nodes) - 1 else "\\-- "
        status_icon = "[OK]" if node.status in ("success", "committed", "completed") else "[FAIL]"
        tool_info = f" -> {node.tool_name}" if node.tool_name else ""
        agent_info = f"[{node.agent_id}]" if node.agent_id else "[unknown]"
        worktree_info = f" ({node.worktree_path})" if node.worktree_path else ""

        line = f"{prefix}{status_icon} Node: {node.id} {agent_info}{tool_info}{worktree_info}"
        lines.append(line)

        # Metadata or prompt snapshot preview
        if node.prompt_snapshot:
            snippet = node.prompt_snapshot.strip().replace("\n", " ")[:60]
            lines.append(f"    |   Prompt: \"{snippet}...\"")
        elif node.metadata:
            snippet = str(node.metadata)[:60]
            lines.append(f"    |   Detail: {snippet}")

    lines.append("==============================\n")
    return "\n".join(lines)


def cmd_log(session_id: str, db_path: str = "graph.db") -> str:
    """Retrieves session nodes from SQLite and returns formatted tree string."""
    storage = FullerenceStorage(db_path=db_path)
    nodes = storage.get_session_nodes(session_id)
    return format_causal_tree(nodes)
