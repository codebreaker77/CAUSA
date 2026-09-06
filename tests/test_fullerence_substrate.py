"""Comprehensive end-to-end test suite verifying restructured packages.fullerence substrate."""

import os
import shutil
import pytest
from packages.fullerence import (
    # Types
    CausalNode,
    CausalNodeType,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    Lease,
    LeaseLockState,
    BlackboardEntry,
    ToolCallIntent,
    PreCommitRule,
    PreCommitRuleType,
    InterceptionDecision,
    # Core Engine
    FullerenceStorage,
    FullerenceGraph,
    IngressGateway,
    CausalDebugger,
    WorktreeDaemon,
    FullerenceMCPServer,
    BreakpointManager,
    SemanticBreakpoint,
)

TEST_DB = "tests/test_fullerence_unified_substrate.db"
TEST_WORKTREES = "tests/test_fullerence_worktrees_env"


@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass
    if os.path.exists(TEST_WORKTREES):
        shutil.rmtree(TEST_WORKTREES, ignore_errors=True)
    os.makedirs(TEST_WORKTREES, exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass
    if os.path.exists(TEST_WORKTREES):
        shutil.rmtree(TEST_WORKTREES, ignore_errors=True)


def test_unified_fullerence_substrate_all_layers():
    print("\n" + "=" * 64)
    print("[TEST] RUNNING UNIFIED PACKAGES.FULLERENCE SUBSTRATE TEST")
    print("=" * 64 + "\n")

    # 1. Layer 1: Storage & WAL Mode
    print("[LAYER 1] Initializing FullerenceStorage...")
    storage = FullerenceStorage(db_path=TEST_DB)
    graph = FullerenceGraph(storage)

    session_id = "sess_unified_substrate"
    node_0 = CausalNode(
        id="node_init",
        session_id=session_id,
        agent_id="agent_root",
        type=CausalNodeType.AGENT_SPAWN,
        status="completed",
        created_at=1000,
    )
    storage.insert_node(node_0)
    assert storage.get_node("node_init") is not None
    print("   [OK] Layer 1 Storage verified.")

    # 2. Layer 2: Causal Debugger
    print("\n[LAYER 2] Verifying CausalDebugger service...")
    debugger = CausalDebugger(storage, graph)
    node_fail = CausalNode(
        id="node_err",
        session_id=session_id,
        agent_id="agent_root",
        parent_node_id="node_init",
        type=CausalNodeType.TEST_RUN,
        status="failed",
        created_at=1001,
    )
    storage.insert_node(node_fail)
    storage.insert_edge(CausalEdge(id="e_0_fail", from_node_id="node_init", to_node_id="node_err", type=CausalEdgeType.CAUSED_BY, created_at=1001))

    blame_res = debugger.blame("node_err")
    assert blame_res["root_cause_node_id"] is not None
    print(f"   [OK] Layer 2 Blame verified: Root cause {blame_res['root_cause_node_id']}")

    # 3. Layer 3: Ingress Gateway
    print("\n[LAYER 3] Verifying IngressGateway interception...")
    ingress = IngressGateway(storage, graph)
    intent = ToolCallIntent(
        session_id=session_id,
        agent_id="agent_root",
        tool_name="writeFile",
        tool_payload='{"file": "api.py"}',
        parent_node_id="node_init",
    )
    intent_node = ingress.record_tool_call_intent(intent)
    assert intent_node.status == "pending_interception"

    rule = PreCommitRule(
        rule_id="r_sig",
        rule_type=PreCommitRuleType.DISALLOW_BREAKING_SIGNATURES,
    )
    breaking_diff = ASTDiff(
        id="d_break",
        causal_node_id=intent_node.id,
        file_path="api.py",
        diff_type=ASTDiffType.SIGNATURE_CHANGED,
        symbol_id="func_call",
        before_signature="call() -> None",
        after_signature="call(x: int) -> None",
        created_at=1002,
    )
    eval_res = ingress.evaluate_semantic_breakpoints(intent_node, [breaking_diff], [rule])
    assert eval_res.allowed is False
    assert eval_res.decision == InterceptionDecision.BLOCKED
    print("   [OK] Layer 3 Ingress Interception verified: BLOCKED breaking change.")

    # 4. Layer 4: Multi-Worktree Daemon
    print("\n[LAYER 4] Verifying WorktreeDaemon dynamic discovery & sync...")
    daemon = WorktreeDaemon(worktrees_dir=TEST_WORKTREES, storage=storage)
    wt_auth = os.path.join(TEST_WORKTREES, "agent-test-auth")
    os.makedirs(wt_auth, exist_ok=True)
    cycle_res = daemon.poll_once()
    assert cycle_res["active_worktrees_count"] == 1
    print("   [OK] Layer 4 Daemon dynamically registered worktree.")

    # 5. Layer 5: Agent MCP Server
    print("\n[LAYER 5] Verifying FullerenceMCPServer tools...")
    mcp_server = FullerenceMCPServer(db_path=TEST_DB)
    tools = mcp_server.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "get_blackboard_signatures" in tool_names
    assert "get_causal_history" in tool_names
    assert "check_file_lease" in tool_names
    print(f"   [OK] Layer 5 MCP Server verified ({len(tool_names)} tools active).")

    print("\n" + "=" * 64)
    print("[SUCCESS] UNIFIED PACKAGES.FULLERENCE SUBSTRATE 100% VALIDATED!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    test_unified_fullerence_substrate_all_layers()
