"""Causal Debugger engine integrated into Fullerence substrate."""

from typing import Dict, Any, List, Set, Optional
from collections import deque
from sqlalchemy import text
from packages.fullerence.types import (
    CausalNode,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    SemanticBreakpoint,
    BreakpointManager,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph


# -------------------------------------------------------------
# 1. First-Bad-Decision Localization
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# 2. Transitive Taint Invalidation & Blast Radius
# -------------------------------------------------------------
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

    visited: Set[str] = {corrupt_node_id}
    queue = deque([corrupt_node_id])
    direct_children_count = 0

    while queue:
        curr_id = queue.popleft()
        if curr_id != corrupt_node_id:
            tainted_node_ids.append(curr_id)
            node = storage.get_node(curr_id)
            if node:
                tainted_agent_ids.add(node.agent_id)
                if node.worktree_path:
                    tainted_worktrees.add(node.worktree_path)
            for diff in storage.get_node_ast_diffs(curr_id):
                contaminated_files.add(diff.file_path)

        # Forward edges in SQLite
        outgoing = storage.get_outgoing_edges(curr_id)
        for edge in outgoing:
            if edge.to_node_id not in visited:
                visited.add(edge.to_node_id)
                queue.append(edge.to_node_id)
                if curr_id == corrupt_node_id:
                    direct_children_count += 1

        # Anyone who read blackboard from this node
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
        "tainted_worktrees": sorted(list(tainted_worktrees)),
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
    if diffs and diffs[0].diff_type == ASTDiffType.SIGNATURE_CHANGED:
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


# -------------------------------------------------------------
# 3. Token Context Attribution View
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# 4. CausalDebugger Service Wrapper
# -------------------------------------------------------------
class CausalDebugger:
    """Unified debugger service over Fullerence substrate."""

    def __init__(self, storage: FullerenceStorage, graph: Optional[FullerenceGraph] = None) -> None:
        self.storage = storage
        self.graph = graph or FullerenceGraph(storage)
        self.breakpoints = BreakpointManager()

    def blame(self, failure_node_id: str) -> Dict[str, Any]:
        """Pinpoints root-cause agent and breaking AST change."""
        return localize_first_bad_decision(self.storage, self.graph, failure_node_id)

    def get_blast_radius(self, corrupt_node_id: str) -> Dict[str, Any]:
        """Calculates transitive taint across agents, worktrees, and files."""
        return get_transitive_taint_set(self.storage, self.graph, corrupt_node_id)

    def plan_rollback(self, corrupt_node_id: str) -> Dict[str, Any]:
        """Computes clean checkpoint and executable git reset command."""
        return compute_counterfactual_fork_point(self.storage, self.graph, corrupt_node_id)

    def inspect_attribution(self, node_id: str) -> Dict[str, Any]:
        """Returns categorized context slices explaining LLM reasoning."""
        return get_attribution_view(self.storage, node_id)
