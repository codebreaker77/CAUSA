"""Command: fullerenes inspect <nodeId> - Token Context Attribution view."""

from typing import Dict, Any, List
from packages.fullerence.storage import FullerenceStorage
from packages.debugger.attribution import get_attribution_view


def format_attribution_view(view: Dict[str, Any]) -> str:
    """Formats the token context attribution view."""
    slices = view.get("active_context_slices", [])
    prompt_len = len(view.get("full_prompt") or "")

    lines: List[str] = [
        "\n================ TOKEN CONTEXT ATTRIBUTION ================",
        f"  Node ID           : {view['node_id']}",
        f"  Agent ID          : {view['agent_id']}",
        f"  Step Type         : {view['step_type']}",
        f"  Prompt Length     : {prompt_len} chars",
        "",
        "--- ACTIVE CONTEXT SLICES ---",
    ]

    for s in slices:
        stype = s.get("type", "unknown").upper()
        source = s.get("source", "")
        excerpt = s.get("excerpt", "")[:60].replace("\n", " ")
        lines.append(
            f"  [{stype:<22}] ({source}) | \"{excerpt}...\""
        )

    lines.append("===========================================================\n")
    return "\n".join(lines)


def cmd_inspect(node_id: str, db_path: str = "graph.db") -> str:
    """Extracts and formats the prompt token attribution view for a node."""
    storage = FullerenceStorage(db_path=db_path)
    view = get_attribution_view(storage, node_id)
    return format_attribution_view(view)
