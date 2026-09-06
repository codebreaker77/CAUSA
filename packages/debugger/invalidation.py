"""Transitive causal invalidation and counterfactual time-travel execution engine."""

from typing import Dict, Any, List, Set
from sqlalchemy import text
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph


def get_transitive_taint_set(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    corrupt_node_id: str,
) -> Dict[str, Any]:
    """Computes all downstream nodes, agents, worktrees, and files tainted by a corrupt node."""
    corrupt_node = storage.get_node(corrupt_node_id)
    if not corrupt_node:
        raise ValueError(f"Corrupt node not found: {corrupt_node_id}")

    tainted_node_ids: List[str] = []
    tainted_agent_ids: Set[str] = {corrupt_node.agent_id}
    tainted_worktrees: Set[str] = {corrupt_node.worktree_path} if corrupt_node.worktree_path else set()
    contaminated_files: Set[str] = set()

    for diff in storage.get_node_ast_diffs(corrupt_node_id):
        contaminated_files.add(diff.file_path)

    visited = {corrupt_node_id}
    queue = [corrupt_node_id]
    direct_children_count = 0

    while queue:
        curr_id = queue.pop(0)
        tainted_node_ids.append(curr_id)

        curr_node = storage.get_node(curr_id)
        if curr_node:
            tainted_agent_ids.add(curr_node.agent_id)
            if curr_node.worktree_path:
                tainted_worktrees.add(curr_node.worktree_path)
            for diff in storage.get_node_ast_diffs(curr_id):
                contaminated_files.add(diff.file_path)

        # 1. Forward edges in SQLite
        outgoing = storage.get_outgoing_edges(curr_id)
        for edge in outgoing:
            if edge.to_node_id not in visited:
                visited.add(edge.to_node_id)
                queue.append(edge.to_node_id)
                if curr_id == corrupt_node_id:
                    direct_children_count += 1

        # 2. Anyone who read blackboard from this node
        with storage.get_session() as session:
            readers = session.execute(
                text(
                    "SELECT from_node_id, to_node_id FROM causal_edges "
                    "WHERE (to_node_id = :id OR from_node_id = :id) AND type = 'read_blackboard'"
                ),
                {"id": curr_id},
            ).fetchall()
            for r in readers:
                other_id = r[0] if r[1] == curr_id else r[1]
                if other_id not in visited:
                    visited.add(other_id)
                    queue.append(other_id)
                    if curr_id == corrupt_node_id:
                        direct_children_count += 1

    return {
        "corrupt_node_id": corrupt_node_id,
        "tainted_node_ids": tainted_node_ids,
        "tainted_agent_ids": sorted(list(tainted_agent_ids)),
        "tainted_worktree_paths": sorted(list(tainted_worktrees)),
        "contaminated_files": sorted(list(contaminated_files)),
        "direct_children_count": direct_children_count,
        "total_tainted_count": len(tainted_node_ids),
    }


def compute_counterfactual_fork_point(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    corrupt_node_id: str,
) -> Dict[str, Any]:
    """Calculates clean ancestor commit, target worktree, and git reset rollback plan."""
    corrupt_node = storage.get_node(corrupt_node_id)
    if not corrupt_node:
        raise ValueError(f"Corrupt node not found: {corrupt_node_id}")

    clean_ancestor_id = corrupt_node.parent_node_id
    clean_commit = "HEAD~1"
    clean_prompt = None

    if clean_ancestor_id:
        ancestor = storage.get_node(clean_ancestor_id)
        if ancestor:
            clean_commit = ancestor.git_commit_hash or "HEAD~1"
            clean_prompt = ancestor.prompt_snapshot

    target_worktree = corrupt_node.worktree_path or ".causa/worktrees/default"
    reset_command = f'git -C "{target_worktree}" reset --hard {clean_commit}'

    taint_info = get_transitive_taint_set(storage, graph, corrupt_node_id)

    diffs = storage.get_node_ast_diffs(corrupt_node_id)
    correction = "Ensure exported interfaces remain backwards-compatible."
    if diffs and diffs[0].diff_type == "signature_changed":
        correction = f"Preserve contract for {diffs[0].before_signature or 'original'} or add default values."

    return {
        "corrupt_node_id": corrupt_node_id,
        "clean_ancestor_node_id": clean_ancestor_id or corrupt_node_id,
        "clean_git_commit_hash": clean_commit,
        "target_worktree_path": target_worktree,
        "reset_command": reset_command,
        "clean_prompt_snapshot": clean_prompt,
        "suggested_correction_constraint": correction,
        "invalidated_descendant_count": taint_info["total_tainted_count"],
    }
