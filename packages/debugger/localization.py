"""First-Bad-Decision backward causal traversal and root-cause localization."""

from typing import Dict, Any, List, Optional
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph


def localize_first_bad_decision(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    failure_node_id: str,
) -> Dict[str, Any]:
    """Starts at a failed test or breakpoint node, backtracks along causal edges,

    and identifies the earliest divergence point / breaking contract.
    """
    failure_node = storage.get_node(failure_node_id)
    if not failure_node:
        raise ValueError(f"Failure node not found: {failure_node_id}")

    causal_path: List[str] = [failure_node_id]
    current_node = failure_node
    root_cause_node = failure_node
    divergence_reason = "Unverified failure point"
    faulty_diff = None

    visited = {failure_node_id}

    while True:
        # 1. Check if current node introduced a breaking AST diff
        diffs = storage.get_node_ast_diffs(current_node.id)
        breaking = next(
            (d for d in diffs if d.diff_type in ("signature_changed", "deleted_export")),
            None,
        )
        if breaking:
            root_cause_node = current_node
            faulty_diff = breaking
            diff_type_str = (
                breaking.diff_type.value
                if hasattr(breaking.diff_type, "value")
                else str(breaking.diff_type)
            )
            divergence_reason = (
                f"Breaking AST mutation in {breaking.file_path}: {diff_type_str} "
                f"(before: {breaking.before_signature or 'none'}, after: {breaking.after_signature or 'none'})"
            )
            break

        # 2. Check for incoming cross-agent blackboard dependency
        incoming = storage.get_incoming_edges(current_node.id)
        outgoing = storage.get_outgoing_edges(current_node.id)

        # Check blackboard reading in either edge orientation
        bb_read = next(
            (e for e in outgoing if e.type == "read_blackboard"),
            next((e for e in incoming if e.type == "read_blackboard"), None),
        )

        upstream_bb_id = None
        if bb_read:
            upstream_bb_id = (
                bb_read.to_node_id if bb_read.from_node_id == current_node.id else bb_read.from_node_id
            )

        if upstream_bb_id and upstream_bb_id not in visited:
            upstream_node = storage.get_node(upstream_bb_id)
            if upstream_node:
                visited.add(upstream_node.id)
                causal_path.append(upstream_node.id)
                current_node = upstream_node
                root_cause_node = upstream_node
                divergence_reason = (
                    f"Cross-agent taint: Agent {current_node.agent_id} read invalid blackboard export "
                    f"from {upstream_node.agent_id} at {upstream_node.id}"
                )
                continue

        # 3. Follow backward caused_by edge or parent_node_id
        caused_by = next((e for e in incoming if e.type == "caused_by"), None)
        prev_id = caused_by.from_node_id if caused_by else current_node.parent_node_id

        if prev_id and prev_id not in visited:
            prev_node = storage.get_node(prev_id)
            if prev_node:
                visited.add(prev_id)
                causal_path.append(prev_id)
                current_node = prev_node

                # Check if prompt introduced a false assumption
                if (
                    prev_node.type == "prompt_step"
                    and prev_node.prompt_snapshot
                    and ("assume" in prev_node.prompt_snapshot.lower() or prev_node.status == "faulty")
                ):
                    root_cause_node = prev_node
                    divergence_reason = f"Flawed prompt hypothesis at step {prev_node.id}"
                    break

                root_cause_node = prev_node
                continue

        break

    return {
        "failure_node_id": failure_node_id,
        "root_cause_node_id": root_cause_node.id,
        "divergence_reason": divergence_reason,
        "causal_path": causal_path,
        "faulty_agent_id": root_cause_node.agent_id,
        "faulty_commit_hash": root_cause_node.git_commit_hash,
        "faulty_prompt_snapshot": root_cause_node.prompt_snapshot,
        "faulty_diff": faulty_diff.model_dump() if faulty_diff else None,
    }
