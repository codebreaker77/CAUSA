"""Simulation test for Layer 1: Schema & Data Models in Fullerence Storage."""

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

TEST_DB_PATH = "tests/test_causa_layer1.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


def test_layer1_storage_simulation():
    print("\n================================================================")
    print("[TEST] RUNNING PYTHON LAYER 1 SIMULATION: FULLERENCE STORAGE & SCHEMA")
    print("================================================================\n")

    storage = FullerenceStorage(db_path=TEST_DB_PATH)
    session_id = "session_python_demo_001"

    # 1. Agent A Spawns in Git Worktree
    print("[STEP 1] Agent A Spawns in Git Worktree (Astra)...")
    node_a1 = CausalNode(
        id="node_001",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="c0_clean_9a8f",
        type=CausalNodeType.AGENT_SPAWN,
        tool_name="astra_spawn",
        tool_payload='{"objective": "Implement rotateToken"}',
        status="success",
        created_at=1000,
    )
    storage.insert_node(node_a1)
    print(f"   [OK] [agent_spawn] logged -> Node: {node_a1.id} ({node_a1.worktree_path})")

    # 2. Agent A Context Tokens / Prompt Snapshot (Step T Persistence)
    print("[STEP 2] Agent A Prompt Execution (Exact Context Tokens Snapshot)...")
    prompt_text = "System: Autonomous Auth Agent. Scope: auth/token.py. Objective: Add old_token parameter."
    node_a2 = CausalNode(
        id="node_002",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="c0_clean_9a8f",
        parent_node_id=node_a1.id,
        prompt_hash="sha256_prompt_step_02",
        prompt_snapshot=prompt_text,
        type=CausalNodeType.PROMPT_STEP,
        status="success",
        created_at=1001,
    )
    storage.insert_node(node_a2)
    storage.insert_edge(
        CausalEdge(
            id="edge_001",
            from_node_id=node_a1.id,
            to_node_id=node_a2.id,
            type=CausalEdgeType.CAUSED_BY,
            created_at=1001,
        )
    )
    print(f"   [OK] [prompt_step] logged -> Node: {node_a2.id} (Hash: {node_a2.prompt_hash})")
    print(f"   [OK] Causal edge [caused_by]: {node_a1.id} --> {node_a2.id}")

    # 3. Ferry Pre-Commit Lease
    print("[STEP 3] Ferry Pre-Commit Locking (Leases Log)...")
    lease = Lease(
        id="lease_001",
        agent_id="agent_auth",
        file_path="auth/token.py",
        lock_state=LeaseLockState.ACQUIRED,
        timestamp=1002,
    )
    storage.record_lease(lease)
    active_lease = storage.get_active_lease("auth/token.py")
    assert active_lease is not None
    assert active_lease.agent_id == "agent_auth"
    print(f"   [OK] Active lock verified: {active_lease.file_path} locked by {active_lease.agent_id}")

    # 4. File Mutation & AST Diff
    print("[STEP 4] File Mutation & Semantic AST Diff Recording...")
    node_a3 = CausalNode(
        id="node_003",
        session_id=session_id,
        agent_id="agent_auth",
        worktree_path=".causa/worktrees/agent-auth",
        git_commit_hash="c1_mutated_7b2c",
        parent_node_id=node_a2.id,
        type=CausalNodeType.FILE_MUTATION,
        tool_name="writeFile",
        tool_payload='{"file": "auth/token.py"}',
        status="success",
        created_at=1003,
    )
    storage.insert_node(node_a3)
    storage.insert_edge(
        CausalEdge(
            id="edge_002",
            from_node_id=node_a2.id,
            to_node_id=node_a3.id,
            type=CausalEdgeType.CAUSED_BY,
            created_at=1003,
        )
    )

    diff = ASTDiff(
        id="diff_001",
        causal_node_id=node_a3.id,
        file_path="auth/token.py",
        diff_type=ASTDiffType.SIGNATURE_CHANGED,
        symbol_id="func_rotateToken",
        before_signature="rotateToken(user_id: str) -> TokenPair",
        after_signature="rotateToken(user_id: str, old_token: str) -> TokenPair",
        raw_diff="+ old_token: str parameter added",
        created_at=1003,
    )
    storage.insert_ast_diff(diff)
    print(f"   [OK] AST Diff recorded: {diff.diff_type.value} on {diff.symbol_id}")
    print(f"        Before: {diff.before_signature}")
    print(f"        After : {diff.after_signature}")

    # 5. Shared SQLite Blackboard
    print("[STEP 5] Shared SQLite Blackboard Broadcast...")
    bb_entry = BlackboardEntry(
        id="bb_001",
        symbol_id="func_rotateToken",
        name="rotateToken",
        signature="rotateToken(user_id: str, old_token: str) -> TokenPair",
        file_path="auth/token.py",
        agent_id="agent_auth",
        updated_at=1004,
    )
    storage.update_blackboard(bb_entry)
    bb_entries = storage.get_blackboard()
    assert len(bb_entries) == 1
    assert bb_entries[0].name == "rotateToken"
    print(f"   [OK] Blackboard broadcast verified: {bb_entries[0].name} -> {bb_entries[0].signature}")

    # 6. Agent B Reads Blackboard
    print("[STEP 6] Agent B Spawns & Consumes Blackboard Interface...")
    node_b1 = CausalNode(
        id="node_004",
        session_id=session_id,
        agent_id="agent_test",
        worktree_path=".causa/worktrees/agent-test",
        git_commit_hash="b0_clean_112a",
        type=CausalNodeType.PROMPT_STEP,
        prompt_snapshot="Write tests for rotateToken(user_id, old_token)",
        status="success",
        created_at=1005,
    )
    storage.insert_node(node_b1)
    storage.insert_edge(
        CausalEdge(
            id="edge_003",
            from_node_id=node_b1.id,
            to_node_id=node_a3.id,
            type=CausalEdgeType.READ_BLACKBOARD,
            metadata="rotateToken",
            created_at=1005,
        )
    )
    print(f"   [OK] Cross-agent causal dependency: {node_b1.id} --> {node_a3.id}")

    # 7. Verification & Zero-Loss Asserts
    print("[STEP 7] Running Zero-Loss Ingestion Verifications...")
    session_nodes = storage.get_session_nodes(session_id)
    assert len(session_nodes) == 4
    print(f"   * Session nodes count: {len(session_nodes)} (Expected: 4)")

    retrieved_prompt = storage.get_node(node_a2.id)
    assert retrieved_prompt is not None
    assert retrieved_prompt.prompt_snapshot == prompt_text
    print("   * Zero-loss prompt token persistence: VERIFIED")

    retrieved_diffs = storage.get_node_ast_diffs(node_a3.id)
    assert len(retrieved_diffs) == 1
    assert retrieved_diffs[0].diff_type == ASTDiffType.SIGNATURE_CHANGED
    print("   * AST diff retrieval: VERIFIED")

    outgoing_edges = storage.get_outgoing_edges(node_b1.id)
    assert len(outgoing_edges) == 1
    assert outgoing_edges[0].type == CausalEdgeType.READ_BLACKBOARD
    print("   * Cross-agent edge retrieval: VERIFIED")

    print("\n================================================================")
    print("[SUCCESS] PYTHON LAYER 1 PASSED: STORAGE & DATA MODELS 100% VALIDATED!")
    print("================================================================\n")


if __name__ == "__main__":
    test_layer1_storage_simulation()
