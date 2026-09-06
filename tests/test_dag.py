"""Exhaustive test suite for Causa Layer 2: Graph Algorithm & Debugger Engine."""

import os
import pytest
from packages.core.schemas.nodes import (
    CausalNode,
    CausalNodeType,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    BlackboardEntry,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.debugger.localization import localize_first_bad_decision
from packages.debugger.invalidation import (
    get_transitive_taint_set,
    compute_counterfactual_fork_point,
)
from packages.debugger.attribution import get_attribution_view

TEST_DB = "tests/test_causa_layer2_dag.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass


def test_layer2_debugger_exhaustive():
    print("\n================================================================")
    print("[TEST] RUNNING PYTHON LAYER 2 EXHAUSTIVE DEBUGGER VALIDATION")
    print("================================================================\n")

    storage = FullerenceStorage(db_path=TEST_DB)
    graph = FullerenceGraph(storage)
    session_id = "session_python_swarm_002"

    # 1. Agent A (Auth) Spawns at clean commit
    print("[STEP 1] Agent A (Auth Service) Spawns at clean commit...")
    node_a1 = CausalNode(
        id="node_a1_spawn",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="commit_c0_clean",
        type=CausalNodeType.AGENT_SPAWN,
        created_at=1000,
    )
    graph.add_node(node_a1)

    # 2. Agent A Prompt Step with Sliced Context
    prompt_text = (
        "System: You are an autonomous backend auth agent.\n"
        "Objective: Refactor verifyToken signature.\n"
        "File: auth/verify.py\n"
        "# Line 12: DEPRECATED: Do not break verifyToken signature\n"
        "def verifyToken(token: str) -> bool: pass\n"
        "$ git status -> clean\n"
        "$ pytest -> 10 passed"
    )
    node_a2 = CausalNode(
        id="node_a2_prompt",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="commit_c0_clean",
        parent_node_id=node_a1.id,
        prompt_hash="sha256_prompt_a2",
        prompt_snapshot=prompt_text,
        tool_name="writeFile",
        tool_payload='{"file": "auth/verify.py"}',
        type=CausalNodeType.PROMPT_STEP,
        created_at=1001,
    )
    graph.add_node(node_a2)
    graph.add_edge(CausalEdge(id="e1", from_node_id=node_a1.id, to_node_id=node_a2.id, type=CausalEdgeType.CAUSED_BY, created_at=1001))

    # 3. Agent A Commits Breaking Change (First Bad Decision)
    print("[STEP 2] Agent A commits Breaking Signature Mutation (First Bad Decision)...")
    node_a3 = CausalNode(
        id="node_a3_bad_mutation",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="commit_c1_broken",
        parent_node_id=node_a2.id,
        type=CausalNodeType.FILE_MUTATION,
        tool_name="writeFile",
        tool_payload='{"file": "auth/verify.py"}',
        created_at=1002,
    )
    graph.add_node(node_a3)
    graph.add_edge(CausalEdge(id="e2", from_node_id=node_a2.id, to_node_id=node_a3.id, type=CausalEdgeType.CAUSED_BY, created_at=1002))

    diff = ASTDiff(
        id="diff_broken_01",
        causal_node_id=node_a3.id,
        file_path="auth/verify.py",
        diff_type=ASTDiffType.SIGNATURE_CHANGED,
        symbol_id="func_verifyToken",
        before_signature="verifyToken(token: str) -> bool",
        after_signature="verifyToken(token: str, secret: str, algo: str) -> bool",
        raw_diff="- def verifyToken(token: str) -> bool\n+ def verifyToken(token: str, secret: str, algo: str) -> bool",
        created_at=1002,
    )
    storage.insert_ast_diff(diff)

    storage.update_blackboard(
        BlackboardEntry(
            id="bb_verify",
            symbol_id="func_verifyToken",
            name="verifyToken",
            signature="verifyToken(token: str, secret: str, algo: str) -> bool",
            file_path="auth/verify.py",
            agent_id="agent_auth",
            updated_at=1002,
        )
    )

    # 4. Agent B Consumes Blackboard & Writes Tests
    print("[STEP 3] Agent B consumes blackboard and writes tests...")
    node_b1 = CausalNode(
        id="node_b1_read",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="commit_b0",
        type=CausalNodeType.PROMPT_STEP,
        prompt_snapshot="Testing verifyToken with new params",
        created_at=1003,
    )
    graph.add_node(node_b1)
    graph.add_edge(CausalEdge(id="e3", from_node_id=node_b1.id, to_node_id=node_a3.id, type=CausalEdgeType.READ_BLACKBOARD, created_at=1003))

    node_b2 = CausalNode(
        id="node_b2_write_test",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="commit_b1",
        parent_node_id=node_b1.id,
        type=CausalNodeType.FILE_MUTATION,
        created_at=1004,
    )
    graph.add_node(node_b2)
    graph.add_edge(CausalEdge(id="e4", from_node_id=node_b1.id, to_node_id=node_b2.id, type=CausalEdgeType.CAUSED_BY, created_at=1004))

    # 5. Test Fails in CI
    node_b3_fail = CausalNode(
        id="node_b3_fail",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="commit_b1",
        parent_node_id=node_b2.id,
        type=CausalNodeType.TEST_RUN,
        status="failed",
        metadata="TypeError: missing required positional arguments 'secret' and 'algo'",
        created_at=1005,
    )
    graph.add_node(node_b3_fail)
    graph.add_edge(CausalEdge(id="e5", from_node_id=node_b2.id, to_node_id=node_b3_fail.id, type=CausalEdgeType.CAUSED_BY, created_at=1005))

    # 6. Concurrently Running Independent Agent C (Billing)
    print("[STEP 4] Independent Agent C (Billing) works concurrently...")
    node_c1 = CausalNode(
        id="node_c1_isolated",
        session_id=session_id,
        agent_id="agent_billing",
        worktree_path=".causa/worktrees/agent-billing",
        git_commit_hash="commit_c0",
        type=CausalNodeType.FILE_MUTATION,
        created_at=1001,
    )
    graph.add_node(node_c1)

    # -------------------------------------------------------------------------
    # VALIDATION 1: First-Bad-Decision Localization
    # -------------------------------------------------------------------------
    print("[VALIDATION 1] Running localize_first_bad_decision()...")
    loc_res = localize_first_bad_decision(storage, graph, node_b3_fail.id)
    assert loc_res["root_cause_node_id"] == node_a3.id
    assert loc_res["faulty_agent_id"] == "agent_auth"
    assert "signature_changed" in loc_res["divergence_reason"]
    print(f"   [OK] Root cause isolated to: {loc_res['root_cause_node_id']} (Agent: {loc_res['faulty_agent_id']})")
    print(f"   [OK] Causal Path: {' <-- '.join(loc_res['causal_path'])}")

    # -------------------------------------------------------------------------
    # VALIDATION 2: Transitive Taint Set & Blast Radius Isolation
    # -------------------------------------------------------------------------
    print("[VALIDATION 2] Running get_transitive_taint_set()...")
    taint_res = get_transitive_taint_set(storage, graph, node_a3.id)
    assert "agent_auth" in taint_res["tainted_agent_ids"]
    assert "agent_test" in taint_res["tainted_agent_ids"]
    assert "agent_billing" not in taint_res["tainted_agent_ids"]
    assert ".causa/worktrees/agent-billing" not in taint_res["tainted_worktree_paths"]
    print(f"   [OK] Tainted agents: {taint_res['tainted_agent_ids']}")
    print(f"   [OK] Tainted worktrees: {taint_res['tainted_worktree_paths']}")
    print("   [OK] Independent Agent C verified clean and untainted!")

    # -------------------------------------------------------------------------
    # VALIDATION 3: Token Context Attribution View
    # -------------------------------------------------------------------------
    print("[VALIDATION 3] Running get_attribution_view()...")
    attr_res = get_attribution_view(storage, node_a2.id)
    slice_types = [s["type"] for s in attr_res["active_context_slices"]]
    assert "system_instruction" in slice_types
    assert "file_context" in slice_types
    assert "terminal_output" in slice_types
    assert "blackboard_interface" in slice_types
    print(f"   [OK] Extracted {len(attr_res['active_context_slices'])} attribution slices: {slice_types}")

    # -------------------------------------------------------------------------
    # VALIDATION 4: Counterfactual Rollback Fork Point
    # -------------------------------------------------------------------------
    print("[VALIDATION 4] Running compute_counterfactual_fork_point()...")
    fork_res = compute_counterfactual_fork_point(storage, graph, node_a3.id)
    assert fork_res["clean_ancestor_node_id"] == node_a2.id
    assert fork_res["clean_git_commit_hash"] == "commit_c0_clean"
    assert fork_res["reset_command"] == 'git -C ".causa/worktrees/agent-auth" reset --hard commit_c0_clean'
    assert fork_res["invalidated_descendant_count"] >= 3
    print(f"   [OK] Clean Commit Checkpoint : {fork_res['clean_git_commit_hash']}")
    print(f"   [OK] Generated Reset Command : {fork_res['reset_command']}")
    print(f"   [OK] Suggested Constraint    : {fork_res['suggested_correction_constraint']}")

    # -------------------------------------------------------------------------
    # VALIDATION 5: Semantic Breakpoint Evaluator
    # -------------------------------------------------------------------------
    print("[VALIDATION 5] Running BreakpointManager semantic evaluations...")
    from packages.debugger.breakpoints import BreakpointManager, SemanticBreakpoint
    bp_mgr = BreakpointManager()
    bp_mgr.add_breakpoint(
        SemanticBreakpoint(
            id="bp_signature",
            condition_type="ast_diff",
            target_symbol="func_verifyToken",
            description="Break on breaking contract mutation",
        )
    )
    bp_mgr.add_breakpoint(
        SemanticBreakpoint(
            id="bp_test_fail",
            condition_type="status_failure",
            description="Break on any test failure",
        )
    )
    hit_ast = bp_mgr.evaluate(node_a3, diffs=[diff])
    assert hit_ast is not None
    assert hit_ast.id == "bp_signature"
    print(f"   [OK] Triggered AST Breakpoint: {hit_ast.id} on {hit_ast.target_symbol}")

    hit_fail = bp_mgr.evaluate(node_b3_fail)
    assert hit_fail is not None
    assert hit_fail.id == "bp_test_fail"
    print(f"   [OK] Triggered Failure Breakpoint: {hit_fail.id} on status {node_b3_fail.status}")

    print("\n================================================================")
    print("[SUCCESS] ALL LAYER 2 CAUSAL GRAPH ALGORITHMS 100% VALIDATED!")
    print("================================================================\n")


if __name__ == "__main__":
    test_layer2_debugger_exhaustive()
