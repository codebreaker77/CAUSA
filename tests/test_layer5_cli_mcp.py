"""Comprehensive simulation test suite for Layer 5: CLI & MCP Server."""

import json
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
from packages.fullerence.storage import FullerenceStorage
from packages.cli.commands.log import cmd_log
from packages.cli.commands.blame import cmd_blame
from packages.cli.commands.rollback import cmd_rollback
from packages.cli.commands.inspect import cmd_inspect
from packages.cli.mcp.server import CausaMCPServer

TEST_DB = "tests/test_causa_layer5_cli.db"


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


def test_layer5_cli_and_mcp_simulation():
    print("\n" + "=" * 64)
    print("[TEST] RUNNING PYTHON LAYER 5: CLI & MCP SERVER SIMULATION")
    print("=" * 64 + "\n")

    storage = FullerenceStorage(db_path=TEST_DB)
    session_id = "sess_layer5_demo"

    # Setup multi-agent execution scenario in SQLite
    # Agent Auth: Step 1 (Prompt), Step 2 (Breaking Mutation)
    node_a1 = CausalNode(
        id="node_cli_a1",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="commit_c0_clean",
        type=CausalNodeType.PROMPT_STEP,
        prompt_snapshot="System: maintain backward compatibility.\nFile: auth/token.py\nTask: rotateToken",
        status="completed",
        created_at=1000,
    )
    storage.insert_node(node_a1)

    node_a2 = CausalNode(
        id="node_cli_a2_broken",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="commit_c1_broken",
        parent_node_id=node_a1.id,
        tool_name="writeFile",
        type=CausalNodeType.FILE_MUTATION,
        status="committed",
        created_at=1001,
    )
    storage.insert_node(node_a2)
    storage.insert_edge(CausalEdge(id="e_a1_a2", from_node_id=node_a1.id, to_node_id=node_a2.id, type=CausalEdgeType.CAUSED_BY, created_at=1001))

    diff_a2 = ASTDiff(
        id="diff_cli_a2",
        causal_node_id=node_a2.id,
        file_path="auth/token.py",
        diff_type=ASTDiffType.SIGNATURE_CHANGED,
        symbol_id="func_rotateToken",
        before_signature="rotateToken(user_id: str) -> str",
        after_signature="rotateToken(user_id: str, old_token: str, strict: bool) -> str",
        raw_diff="- def rotateToken(user_id: str) -> str\n+ def rotateToken(user_id: str, old_token: str, strict: bool) -> str",
        created_at=1001,
    )
    storage.insert_ast_diff(diff_a2)

    storage.update_blackboard(
        BlackboardEntry(
            id="bb_rotateToken",
            symbol_id="func_rotateToken",
            name="rotateToken",
            signature="rotateToken(user_id: str, old_token: str, strict: bool) -> str",
            file_path="auth/token.py",
            agent_id="agent_auth",
            updated_at=1001,
        )
    )

    # Agent Test: Step 3 (Read BB), Step 4 (Test Failure)
    node_b1 = CausalNode(
        id="node_cli_b1",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="commit_b0",
        type=CausalNodeType.PROMPT_STEP,
        status="completed",
        created_at=1002,
    )
    storage.insert_node(node_b1)
    storage.insert_edge(CausalEdge(id="e_b1_a2", from_node_id=node_b1.id, to_node_id=node_a2.id, type=CausalEdgeType.READ_BLACKBOARD, created_at=1002))

    node_b2_fail = CausalNode(
        id="node_cli_b2_fail",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="commit_b1",
        parent_node_id=node_b1.id,
        type=CausalNodeType.TEST_RUN,
        status="failed",
        metadata="TypeError: rotateToken missing 2 required positional arguments",
        created_at=1003,
    )
    storage.insert_node(node_b2_fail)
    storage.insert_edge(CausalEdge(id="e_b1_b2", from_node_id=node_b1.id, to_node_id=node_b2_fail.id, type=CausalEdgeType.CAUSED_BY, created_at=1003))

    # Active Lease
    storage.record_lease(
        Lease(
            id="lease_auth",
            agent_id="agent_auth",
            file_path="auth/token.py",
            lock_state=LeaseLockState.ACQUIRED,
            timestamp=1000,
        )
    )

    # -------------------------------------------------------------
    # 1. Test CLI: fullerenes log [sessionId]
    # -------------------------------------------------------------
    print("[STEP 1] Testing CLI: fullerenes log [sessionId]...")
    log_output = cmd_log(session_id, db_path=TEST_DB)
    assert "=== CAUSAL EXECUTION GRAPH ===" in log_output
    assert "node_cli_a1" in log_output
    assert "node_cli_a2_broken" in log_output
    assert "node_cli_b2_fail" in log_output
    assert "[FAIL]" in log_output
    print("   [OK] Tree Output Rendered Successfully:")
    print("   " + "\n   ".join(log_output.strip().splitlines()[:5]) + "\n   ...")

    # -------------------------------------------------------------
    # 2. Test CLI: fullerenes blame <failedNodeId>
    # -------------------------------------------------------------
    print("\n[STEP 2] Testing CLI: fullerenes blame <failedNodeId>...")
    blame_output = cmd_blame(node_b2_fail.id, db_path=TEST_DB)
    assert "FIRST-BAD-DECISION BLAME" in blame_output
    assert node_a2.id in blame_output
    assert "agent_auth" in blame_output
    assert "signature_changed" in blame_output
    print("   [OK] Blame Localization Report Rendered:")
    print("   " + "\n   ".join(blame_output.strip().splitlines()[:6]))

    # -------------------------------------------------------------
    # 3. Test CLI: fullerenes rollback <nodeId>
    # -------------------------------------------------------------
    print("\n[STEP 3] Testing CLI: fullerenes rollback <nodeId>...")
    rollback_output = cmd_rollback(node_a2.id, db_path=TEST_DB)
    assert "COUNTERFACTUAL ROLLBACK PLAN" in rollback_output
    assert "commit_c0_clean" in rollback_output
    assert 'git -C ".causa/worktrees/agent-auth" reset --hard commit_c0_clean' in rollback_output
    assert "agent_test" in rollback_output
    print("   [OK] Counterfactual Rollback Script Rendered:")
    print("   " + "\n   ".join(rollback_output.strip().splitlines()[:7]))

    # -------------------------------------------------------------
    # 4. Test CLI: fullerenes inspect <nodeId>
    # -------------------------------------------------------------
    print("\n[STEP 4] Testing CLI: fullerenes inspect <nodeId>...")
    inspect_output = cmd_inspect(node_a1.id, db_path=TEST_DB)
    assert "TOKEN CONTEXT ATTRIBUTION" in inspect_output
    assert "ACTIVE CONTEXT SLICES" in inspect_output
    print("   [OK] Token Context Attribution Slices Rendered:")
    print("   " + "\n   ".join(inspect_output.strip().splitlines()[:7]))

    # -------------------------------------------------------------
    # 5. Test MCP Server: Tools & JSON-RPC
    # -------------------------------------------------------------
    print("\n[STEP 5] Testing MCP Server Tool Handlers...")
    mcp_server = CausaMCPServer(db_path=TEST_DB)

    # Tool A: get_blackboard_signatures
    bb_res = mcp_server.call_tool("get_blackboard_signatures", {})
    assert bb_res["count"] == 1
    assert bb_res["signatures"][0]["name"] == "rotateToken"
    assert "strict: bool" in bb_res["signatures"][0]["signature"]
    print(f"   [OK] MCP Tool get_blackboard_signatures -> {bb_res['signatures'][0]['signature']}")

    # Tool B: get_causal_history
    hist_res = mcp_server.call_tool("get_causal_history", {"session_id": session_id, "limit": 10})
    assert hist_res["total_nodes"] == 4
    assert len(hist_res["history"]) == 4
    print(f"   [OK] MCP Tool get_causal_history -> Retrieved {len(hist_res['history'])} nodes")

    # Tool C: check_file_lease
    lease_locked = mcp_server.call_tool("check_file_lease", {"file_path": "auth/token.py"})
    assert lease_locked["is_locked"] is True
    assert lease_locked["held_by_agent"] == "agent_auth"

    lease_free = mcp_server.call_tool("check_file_lease", {"file_path": "unlocked/file.py"})
    assert lease_free["is_locked"] is False
    print("   [OK] MCP Tool check_file_lease -> Verified locked vs unlocked files")

    # JSON-RPC Protocol Round-Trip
    rpc_req = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "check_file_lease",
            "arguments": {"file_path": "auth/token.py"},
        },
        "id": "req_101",
    })
    rpc_resp = json.loads(mcp_server.handle_rpc_request(rpc_req))
    assert rpc_resp["id"] == "req_101"
    parsed_content = json.loads(rpc_resp["result"]["content"][0]["text"])
    assert parsed_content["is_locked"] is True
    print(f"   [OK] JSON-RPC 2.0 Dispatcher Verified -> req_101 responded with is_locked=True")

    print("\n" + "=" * 64)
    print("[SUCCESS] LAYER 5: CLI & MCP SERVER 100% VALIDATED!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    test_layer5_cli_and_mcp_simulation()
