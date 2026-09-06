"""Comprehensive simulation test suite for Layer 3: Transport & Interception Gateway."""

import os
import pytest
from packages.core.schemas.nodes import (
    CausalNode,
    CausalNodeType,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    Lease,
    LeaseLockState,
    BlackboardEntry,
)
from packages.core.schemas.ingress import (
    ToolCallIntent,
    PreCommitRule,
    PreCommitRuleType,
    InterceptionDecision,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.fullerence.ingress import IngressGateway
from packages.debugger.breakpoints import BreakpointManager, SemanticBreakpoint

TEST_DB = "tests/test_causa_layer3_ingress.db"


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


def test_layer3_ingress_full_simulation():
    print("\n" + "=" * 64)
    print("[TEST] RUNNING PYTHON LAYER 3: TRANSPORT & INTERCEPTION GATEWAY")
    print("=" * 64 + "\n")

    storage = FullerenceStorage(db_path=TEST_DB)
    graph = FullerenceGraph(storage)
    gateway = IngressGateway(storage, graph)

    session_id = "sess_l3_interception"
    agent_id = "agent_auth"
    worktree = ".causa/worktrees/agent-auth"

    # Step 0: Agent Root Step
    root_node = CausalNode(
        id="node_prompt_001",
        session_id=session_id,
        agent_id=agent_id,
        worktree_path=worktree,
        type=CausalNodeType.PROMPT_STEP,
        prompt_snapshot="Update auth verification token system",
        status="completed",
        created_at=1000,
    )
    storage.insert_node(root_node)
    graph.add_node(root_node)

    # -------------------------------------------------------------
    # 1. Tool Call Intent Logging (In-Flight Before Disk Write)
    # -------------------------------------------------------------
    print("[STEP 1] Logging In-Flight Tool Call Intent...")
    intent = ToolCallIntent(
        session_id=session_id,
        agent_id=agent_id,
        tool_name="writeFile",
        tool_payload='{"file_path": "auth/verify.py", "action": "update_signature"}',
        worktree_path=worktree,
        git_commit_hash="commit_clean_0",
        parent_node_id=root_node.id,
    )

    intent_node = gateway.record_tool_call_intent(intent)
    assert intent_node.status == "pending_interception"
    assert intent_node.type == CausalNodeType.TOOL_CALL
    print(f"   [OK] Intent Node logged: {intent_node.id} (Status: {intent_node.status})")

    # Verify causal edge from root_node to intent_node
    incoming = storage.get_incoming_edges(intent_node.id)
    assert len(incoming) == 1
    assert incoming[0].from_node_id == root_node.id
    assert incoming[0].type == "caused_by"
    print(f"   [OK] Causal Edge connected: {root_node.id} --> {intent_node.id}")

    # -------------------------------------------------------------
    # 2. Rule Configuration
    # -------------------------------------------------------------
    rule_signature = PreCommitRule(
        rule_id="rule_no_breaking_sig",
        rule_type=PreCommitRuleType.DISALLOW_BREAKING_SIGNATURES,
        description="Disallow breaking changes to exported signatures without override.",
    )
    rule_deletion = PreCommitRule(
        rule_id="rule_max_delete",
        rule_type=PreCommitRuleType.MAX_LINES_DELETED,
        max_line_deletions=50,
        description="Disallow deleting more than 50 lines in a single mutation.",
    )
    rule_lease = PreCommitRule(
        rule_id="rule_lease_check",
        rule_type=PreCommitRuleType.ENFORCE_FILE_LEASE,
        description="Disallow mutating files leased by another agent.",
    )
    rules = [rule_signature, rule_deletion, rule_lease]

    # -------------------------------------------------------------
    # 3. Interception Test A: Breaking Signature Change (BLOCKED)
    # -------------------------------------------------------------
    print("\n[STEP 2] Evaluating Interception on Breaking Signature Mutation...")
    breaking_diff = ASTDiff(
        id="diff_breaking_01",
        causal_node_id=intent_node.id,
        file_path="auth/verify.py",
        diff_type=ASTDiffType.SIGNATURE_CHANGED,
        symbol_id="func_verifyToken",
        before_signature="verifyToken(token: str) -> bool",
        after_signature="verifyToken(token: str, secret: str, algo: str) -> bool",
        raw_diff="- def verifyToken(token: str) -> bool\n+ def verifyToken(token: str, secret: str, algo: str) -> bool",
        created_at=1001,
    )

    eval_breaking = gateway.evaluate_semantic_breakpoints(
        node=intent_node,
        ast_diffs=[breaking_diff],
        rules=rules,
    )
    assert eval_breaking.allowed is False
    assert eval_breaking.decision == InterceptionDecision.BLOCKED
    assert "rule_no_breaking_sig" in eval_breaking.violated_rules
    assert eval_breaking.suggested_remedy is not None
    print(f"   [OK] Action Intercepted & BLOCKED!")
    print(f"   [OK] Violated Rule : {eval_breaking.violated_rules}")
    print(f"   [OK] Remedy Notice : {eval_breaking.suggested_remedy}")

    # -------------------------------------------------------------
    # 4. Interception Test B: Massive Deletion (>50 lines) (BLOCKED)
    # -------------------------------------------------------------
    print("\n[STEP 3] Evaluating Interception on Massive Deletion Guard...")
    large_delete_raw = "\n".join([f"- deleted_line_{i}();" for i in range(60)])
    massive_diff = ASTDiff(
        id="diff_massive_del_01",
        causal_node_id=intent_node.id,
        file_path="auth/legacy.py",
        diff_type=ASTDiffType.BODY_CHANGED,
        symbol_id="module_legacy",
        raw_diff=large_delete_raw,
        created_at=1002,
    )

    eval_delete = gateway.evaluate_semantic_breakpoints(
        node=intent_node,
        ast_diffs=[massive_diff],
        rules=rules,
    )
    assert eval_delete.allowed is False
    assert eval_delete.decision == InterceptionDecision.BLOCKED
    assert "rule_max_delete" in eval_delete.violated_rules
    print(f"   [OK] Massive deletion Intercepted & BLOCKED (60 lines > 50 lines threshold)")

    # -------------------------------------------------------------
    # 5. Interception Test C: File Lease Conflict (BLOCKED)
    # -------------------------------------------------------------
    print("\n[STEP 4] Evaluating Interception on File Lease Conflict...")
    storage.record_lease(
        Lease(
            id="lease_billing",
            agent_id="agent_billing",
            file_path="billing/checkout.py",
            lock_state=LeaseLockState.ACQUIRED,
            timestamp=1003,
        )
    )
    conflicting_diff = ASTDiff(
        id="diff_conflict_01",
        causal_node_id=intent_node.id,
        file_path="billing/checkout.py",
        diff_type=ASTDiffType.BODY_CHANGED,
        symbol_id="func_charge",
        created_at=1004,
    )
    eval_conflict = gateway.evaluate_semantic_breakpoints(
        node=intent_node,
        ast_diffs=[conflicting_diff],
        rules=rules,
    )
    assert eval_conflict.allowed is False
    assert "rule_lease_check" in eval_conflict.violated_rules
    print(f"   [OK] Active lease conflict Intercepted & BLOCKED: billing/checkout.py held by agent_billing")

    # -------------------------------------------------------------
    # 6. Interception Test D: Semantic Breakpoint Hit (PAUSED)
    # -------------------------------------------------------------
    print("\n[STEP 5] Evaluating Interception on Semantic Breakpoint...")
    bp_mgr = BreakpointManager()
    bp_mgr.add_breakpoint(
        SemanticBreakpoint(
            id="bp_audit_token",
            condition_type="ast_diff",
            target_symbol="func_safeToken",
            description="Audit sensitive safeToken interface mutation",
        )
    )
    audit_diff = ASTDiff(
        id="diff_audit_01",
        causal_node_id=intent_node.id,
        file_path="auth/safe.py",
        diff_type=ASTDiffType.BODY_CHANGED,
        symbol_id="func_safeToken",
        created_at=1005,
    )
    eval_bp = gateway.evaluate_semantic_breakpoints(
        node=intent_node,
        ast_diffs=[audit_diff],
        rules=[],
        breakpoint_mgr=bp_mgr,
    )
    assert eval_bp.allowed is False
    assert eval_bp.decision == InterceptionDecision.PAUSED_ON_BREAKPOINT
    assert eval_bp.hit_breakpoint_id == "bp_audit_token"
    print(f"   [OK] Execution PAUSED on Breakpoint: {eval_bp.hit_breakpoint_id}")

    # -------------------------------------------------------------
    # 7. Interception Test E: Valid Safe Mutation (ALLOWED)
    # -------------------------------------------------------------
    print("\n[STEP 6] Evaluating Safe Mutation (ALLOWED)...")
    safe_diff = ASTDiff(
        id="diff_safe_01",
        causal_node_id=intent_node.id,
        file_path="auth/verify.py",
        diff_type=ASTDiffType.ADDED_EXPORT,
        symbol_id="func_helperVerify",
        before_signature=None,
        after_signature="helperVerify(token: str) -> bool",
        raw_diff="+ def helperVerify(token: str) -> bool:\n+     return bool(token)",
        created_at=1006,
    )
    eval_safe = gateway.evaluate_semantic_breakpoints(
        node=intent_node,
        ast_diffs=[safe_diff],
        rules=rules,
    )
    assert eval_safe.allowed is True
    assert eval_safe.decision == InterceptionDecision.ALLOWED
    print("   [OK] Pre-commit clearance granted: ALLOWED")

    # -------------------------------------------------------------
    # 8. Atomic Causal Step Commit to SQLite
    # -------------------------------------------------------------
    print("\n[STEP 7] Atomically Committing Step to SQLite...")
    blackboard_update = BlackboardEntry(
        id="bb_helperVerify",
        symbol_id="func_helperVerify",
        name="helperVerify",
        signature="helperVerify(token: str) -> bool",
        file_path="auth/verify.py",
        agent_id=agent_id,
        updated_at=1006,
    )

    committed_node = gateway.commit_causal_step(
        node_id=intent_node.id,
        status="committed",
        ast_diffs=[safe_diff],
        blackboard_entries=[blackboard_update],
    )

    assert committed_node.status == "committed"
    persisted_node = storage.get_node(intent_node.id)
    assert persisted_node is not None
    assert persisted_node.status == "committed"

    # Verify diff was persisted
    node_diffs = storage.get_node_ast_diffs(intent_node.id)
    assert len(node_diffs) == 1
    assert node_diffs[0].symbol_id == "func_helperVerify"

    # Verify blackboard entry updated
    bb_list = storage.get_blackboard()
    assert any(b.symbol_id == "func_helperVerify" for b in bb_list)
    print("   [OK] Atomic transaction verified: Node status updated, ASTDiff stored, Blackboard updated.")

    print("\n" + "=" * 64)
    print("[SUCCESS] LAYER 3: TRANSPORT & INTERCEPTION GATEWAY 100% VALIDATED!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    test_layer3_ingress_full_simulation()
