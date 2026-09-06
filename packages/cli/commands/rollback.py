"""Command: fullerenes rollback <nodeId> - Counterfactual rollback and blast radius."""

from typing import Dict, Any, List
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.debugger.invalidation import (
    compute_counterfactual_fork_point,
    get_transitive_taint_set,
)


def format_rollback_plan(plan: Dict[str, Any], taint: Dict[str, Any]) -> str:
    """Formats the counterfactual rollback diagnosis and git reset script."""
    lines: List[str] = [
        "\n================ COUNTERFACTUAL ROLLBACK PLAN ================",
        f"  Corrupt Node ID       : {plan['corrupt_node_id']}",
        f"  Clean Ancestor Node   : {plan['clean_ancestor_node_id']}",
        f"  Clean Git Checkpoint  : {plan['clean_git_commit_hash']}",
        f"  Target Worktree       : {plan['target_worktree_path']}",
        "",
        "--- BLAST RADIUS INVENTORY ---",
        f"  Tainted Agents        : {', '.join(taint['tainted_agent_ids'])}",
        f"  Tainted Worktrees     : {', '.join(taint['tainted_worktree_paths'])}",
        f"  Contaminated Files    : {', '.join(taint['contaminated_files']) if taint['contaminated_files'] else 'None'}",
        f"  Total Nodes Invalidated: {taint['total_tainted_count']}",
        "",
        "--- SUGGESTED PROMPT CONSTRAINT ---",
        f"  {plan['suggested_correction_constraint']}",
        "",
        "--- EXECUTABLE GIT ROLLBACK SCRIPT ---",
        f"  $ {plan['reset_command']}",
        "==============================================================\n",
    ]
    return "\n".join(lines)


def cmd_rollback(corrupt_node_id: str, db_path: str = "graph.db") -> str:
    """Calculates blast radius and returns executable git rollback plan."""
    storage = FullerenceStorage(db_path=db_path)
    graph = FullerenceGraph(storage)
    plan = compute_counterfactual_fork_point(storage, graph, corrupt_node_id)
    taint = get_transitive_taint_set(storage, graph, corrupt_node_id)
    return format_rollback_plan(plan, taint)
