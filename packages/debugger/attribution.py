"""Token context attribution view: slices prompt tokens, file lines, terminal output."""

from typing import Dict, Any, List
from packages.fullerence.storage import FullerenceStorage


def get_attribution_view(
    storage: FullerenceStorage,
    node_id: str,
) -> Dict[str, Any]:
    """Reconstructs exact token context active at step T and slices attribution highlights."""
    node = storage.get_node(node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    diffs = storage.get_node_ast_diffs(node_id)
    slices: List[Dict[str, str]] = []
    prompt = node.prompt_snapshot or ""

    if prompt:
        lines = prompt.split("\n")
        current_type = "system_instruction"
        current_source = "prompt_header"
        current_lines: List[str] = []

        for line in lines:
            if line.startswith("System:") or line.startswith("Objective:"):
                if current_lines:
                    slices.append({
                        "type": current_type,
                        "source": current_source,
                        "excerpt": "\n".join(current_lines).strip(),
                        "relevance": "Guiding task objective and constraints",
                    })
                    current_lines = []
                current_type = "system_instruction"
                current_source = "system_directive"
                current_lines.append(line)
            elif any(k in line for k in ["File:", ".py", ".ts", "```"]):
                if current_lines:
                    slices.append({
                        "type": current_type,
                        "source": current_source,
                        "excerpt": "\n".join(current_lines).strip(),
                        "relevance": "Code context active in model context window",
                    })
                    current_lines = []
                current_type = "file_context"
                current_source = line.strip("`# ")
                current_lines.append(line)
            elif line.startswith("$") or "Error:" in line or "exit code" in line:
                if current_lines:
                    slices.append({
                        "type": current_type,
                        "source": current_source,
                        "excerpt": "\n".join(current_lines).strip(),
                        "relevance": "Terminal stdout/stderr execution feedback",
                    })
                    current_lines = []
                current_type = "terminal_output"
                current_source = "terminal_feedback"
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            slices.append({
                "type": current_type,
                "source": current_source,
                "excerpt": "\n".join(current_lines).strip(),
                "relevance": "Active prompt slice driving tool invocation",
            })

    # Blackboard cross-reference
    for bb in storage.get_blackboard():
        if bb.name in prompt:
            slices.append({
                "type": "blackboard_interface",
                "source": bb.file_path,
                "excerpt": f"{bb.name}: {bb.signature or 'unknown'}",
                "relevance": f"Shared interface consumed from blackboard (exported by {bb.agent_id})",
            })

    return {
        "node_id": node.id,
        "agent_id": node.agent_id,
        "step_type": node.type.value if hasattr(node.type, "value") else str(node.type),
        "prompt_hash": node.prompt_hash,
        "full_prompt": node.prompt_snapshot,
        "tool_action": node.tool_name,
        "tool_payload": node.tool_payload,
        "active_context_slices": slices,
        "associated_ast_diff": diffs[0].model_dump() if diffs else None,
    }
