"""Comprehensive simulation test suite for Layer 4: Multi-Worktree Daemon."""

import os
import shutil
import time
import pytest
from packages.fullerence.storage import FullerenceStorage
from packages.daemon.watcher import WorktreeWatcher
from packages.daemon.sync import BlackboardSynchronizer
from packages.daemon.service import MultiWorktreeDaemon

TEST_DB = "tests/test_causa_layer4_daemon.db"
TEST_WORKTREES_DIR = "tests/test_worktrees_env"


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Cleanup DB
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass
    # Cleanup Worktrees directory
    if os.path.exists(TEST_WORKTREES_DIR):
        shutil.rmtree(TEST_WORKTREES_DIR, ignore_errors=True)
    os.makedirs(TEST_WORKTREES_DIR, exist_ok=True)

    yield

    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except OSError:
            pass
    if os.path.exists(TEST_WORKTREES_DIR):
        shutil.rmtree(TEST_WORKTREES_DIR, ignore_errors=True)


def test_layer4_multi_worktree_daemon_simulation():
    print("\n" + "=" * 64)
    print("[TEST] RUNNING PYTHON LAYER 4: MULTI-WORKTREE DAEMON SIMULATION")
    print("=" * 64 + "\n")

    storage = FullerenceStorage(db_path=TEST_DB)
    daemon = MultiWorktreeDaemon(worktrees_dir=TEST_WORKTREES_DIR, storage=storage)

    # Initial state: no worktrees
    res_0 = daemon.poll_once()
    assert res_0["active_worktrees_count"] == 0
    print("[STEP 0] Daemon initialized watching .causa/worktrees/ (Active worktrees: 0)")

    # -------------------------------------------------------------
    # 1. Astra Provisions Worktree A (agent-auth)
    # -------------------------------------------------------------
    print("\n[STEP 1] Astra provisions worktree: agent-auth...")
    wt_auth = os.path.join(TEST_WORKTREES_DIR, "agent-auth")
    os.makedirs(os.path.join(wt_auth, "auth"), exist_ok=True)

    res_1 = daemon.poll_once()
    assert res_1["active_worktrees_count"] == 1
    assert os.path.abspath(wt_auth) in res_1["active_worktrees"]
    print(f"   [OK] Daemon dynamically registered watcher for: {wt_auth}")

    # -------------------------------------------------------------
    # 2. Agent Auth Writes session.py with Exported Interface
    # -------------------------------------------------------------
    print("\n[STEP 2] Agent-auth writes auth/session.py with createSession()...")
    session_file = os.path.join(wt_auth, "auth", "session.py")
    with open(session_file, "w", encoding="utf-8") as f:
        f.write(
            "def createSession(user_id: str) -> str:\n"
            '    """Creates a JWT session token."""\n'
            '    return f"jwt_{user_id}"\n'
        )

    # Poll daemon to pick up file change and synchronize AST to blackboard
    res_2 = daemon.poll_once()
    assert res_2["modified_files_count"] >= 1
    assert res_2["synced_symbols_count"] >= 1
    print(f"   [OK] Daemon detected file change and synchronized AST: {res_2['synced_symbols']}")

    # Verify symbol persisted in shared SQLite blackboard
    bb_entries = storage.get_blackboard()
    assert len(bb_entries) == 1
    assert bb_entries[0].symbol_id == "func_createSession"
    assert bb_entries[0].signature == "createSession(user_id: str) -> str"
    assert bb_entries[0].agent_id == "agent-auth"
    print(f"   [OK] SQLite Blackboard contains: {bb_entries[0].name} -> {bb_entries[0].signature}")

    # -------------------------------------------------------------
    # 3. Astra Provisions Worktree B (agent-billing) Concurrently
    # -------------------------------------------------------------
    print("\n[STEP 3] Astra provisions concurrent worktree: agent-billing...")
    wt_billing = os.path.join(TEST_WORKTREES_DIR, "agent-billing")
    os.makedirs(os.path.join(wt_billing, "billing"), exist_ok=True)

    res_3 = daemon.poll_once()
    assert res_3["active_worktrees_count"] == 2
    assert os.path.abspath(wt_billing) in res_3["active_worktrees"]
    print(f"   [OK] Daemon dynamically registered 2nd worktree: {wt_billing}")

    # Verify agent-billing immediately sees agent-auth's exported contract
    billing_view = storage.get_blackboard()
    auth_contract = next((b for b in billing_view if b.symbol_id == "func_createSession"), None)
    assert auth_contract is not None
    assert auth_contract.signature == "createSession(user_id: str) -> str"
    print(f"   [OK] Peer agent-billing can read live interface '{auth_contract.name}' without waiting for a Git merge!")

    # -------------------------------------------------------------
    # 4. Agent Auth Mutates Interface (Live Contract Update)
    # -------------------------------------------------------------
    print("\n[STEP 4] Agent-auth updates createSession signature with tenant_id...")
    time.sleep(0.05)  # Ensure filesystem mtime tick
    with open(session_file, "w", encoding="utf-8") as f:
        f.write(
            "def createSession(user_id: str, tenant_id: str) -> str:\n"
            '    return f"jwt_{tenant_id}_{user_id}"\n'
        )

    res_4 = daemon.poll_once()
    assert res_4["modified_files_count"] >= 1
    bb_updated = storage.get_blackboard()
    auth_updated = next(b for b in bb_updated if b.symbol_id == "func_createSession")
    assert auth_updated.signature == "createSession(user_id: str, tenant_id: str) -> str"
    print(f"   [OK] Live blackboard updated: {auth_updated.signature}")

    # -------------------------------------------------------------
    # 5. Astra Tears Down Worktree A (agent-auth)
    # -------------------------------------------------------------
    print("\n[STEP 5] Astra tears down worktree: agent-auth...")
    shutil.rmtree(wt_auth)

    res_5 = daemon.poll_once()
    assert res_5["active_worktrees_count"] == 1
    assert os.path.abspath(wt_auth) not in res_5["active_worktrees"]
    assert os.path.abspath(wt_billing) in res_5["active_worktrees"]
    print("   [OK] Daemon cleanly unregistered destroyed worktree watcher.")

    print("\n" + "=" * 64)
    print("[SUCCESS] LAYER 4: MULTI-WORKTREE DAEMON 100% VALIDATED!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    test_layer4_multi_worktree_daemon_simulation()
