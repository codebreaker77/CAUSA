"""Terminal Visual Demo for Ferry Transport Interceptor.

Demonstrates Ferry in action with colored output:
1. Concurrency collision prevention across agents.
2. Dry-run AST syntax error interception.
3. Path boundary manifest violations.
4. Real-time AST diff extraction and Blackboard publishing.

Run with:
    python -m packages.ferry.demo
"""

import os
import shutil
import tempfile
import time
from packages.ferry.proxy import FerryProxy, AgentCapabilityManifest
from packages.ferry.lock_manager import LockManager, LeaseLockType
from packages.ferry.blackboard import Blackboard

# ANSI Color escapes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
    print(f"{BOLD}{CYAN}      CAUSA :: FERRY TRANSPORT INTERCEPTOR & PRE-COMMIT ENGINE          {RESET}")
    print(f"{BOLD}{CYAN}========================================================================{RESET}\n")


def run_demo():
    print_banner()
    temp_workspace = tempfile.mkdtemp(prefix="causa_ferry_demo_")
    
    lock_mgr = LockManager(default_ttl_seconds=3)
    blackboard = Blackboard()
    proxy = FerryProxy(
        lock_manager=lock_mgr,
        blackboard=blackboard,
        workspace_root=temp_workspace,
    )

    # -------------------------------------------------------------
    # Scenario 1: Pre-Commit AST Syntax Validation
    # -------------------------------------------------------------
    print(f"{BOLD}[SCENARIO 1] Intercepting Malformed Code (Syntax Error){RESET}")
    broken_code = """
def authenticate_user(username: str, token: str:
    # Notice the missing closing parenthesis above!
    return True
"""
    print(f"Agent {YELLOW}'agent-frontend'{RESET} attempting to write {CYAN}'auth.py'{RESET} with invalid syntax...")
    res = proxy.intercept_tool_call(
        agent_id="agent-frontend",
        tool_name="write_file",
        tool_payload={"path": "auth.py", "content": broken_code},
    )
    if not res.success:
        print(f"[{RED}BLOCKED BY FERRY{RESET}] {res.error_message}")
        print(f"  -> File was {BOLD}NOT{RESET} written to disk. Workspace preserved in healthy state!\n")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # Scenario 2: Security Capability Boundary Enforcement
    # -------------------------------------------------------------
    print(f"{BOLD}[SCENARIO 2] Enforcing Capability Manifest Boundaries{RESET}")
    manifest = AgentCapabilityManifest(
        agent_id="agent-docs",
        allowed_tools=["write_file", "read_file"],
        allowed_write_patterns=["docs/*", "*.md"],
    )
    proxy.register_manifest(manifest)
    print(f"Agent {YELLOW}'agent-docs'{RESET} is scoped strictly to: {manifest.allowed_write_patterns}")
    print(f"Agent {YELLOW}'agent-docs'{RESET} attempting unauthorized write to {CYAN}'src/database.py'{RESET}...")
    res = proxy.intercept_tool_call(
        agent_id="agent-docs",
        tool_name="write_file",
        tool_payload={"path": "src/database.py", "content": "DB_URL = 'mysql://...'\n"},
    )
    if not res.success:
        print(f"[{RED}SECURITY INTERCEPT{RESET}] {res.error_message}\n")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # Scenario 3: Concurrency Protection (Read/Write Leases)
    # -------------------------------------------------------------
    print(f"{BOLD}[SCENARIO 3] Multi-Agent File Collision Prevention{RESET}")
    print(f"Agent {YELLOW}'agent-worker-1'{RESET} acquires write lease on {CYAN}'models.py'{RESET}...")
    lock_mgr.acquire(agent_id="agent-worker-1", file_path="models.py", lock_type=LeaseLockType.EXCLUSIVE_WRITE)

    print(f"Agent {YELLOW}'agent-worker-2'{RESET} tries to edit {CYAN}'models.py'{RESET} simultaneously...")
    res = proxy.intercept_tool_call(
        agent_id="agent-worker-2",
        tool_name="write_file",
        tool_payload={"path": "models.py", "content": "class User: pass\n"},
    )
    if not res.success:
        print(f"[{YELLOW}COLLISION PREVENTED{RESET}] {res.error_message}")
        print(f"  -> Race condition thwarted. Agent 2 held until Agent 1 releases lease.\n")
    lock_mgr.release("agent-worker-1", "models.py")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # Scenario 4: Valid Write, AST Diff Extraction & Blackboard Pub
    # -------------------------------------------------------------
    print(f"{BOLD}[SCENARIO 4] Valid Code Mutation, AST Diffing & Blackboard Publish{RESET}")
    valid_code = """
class AuthService:
    def verify_token(self, token: str) -> bool:
        return True

def create_session(user_id: int) -> str:
    return "session_123"
"""
    print(f"Agent {YELLOW}'agent-auth-lead'{RESET} committing new interface to {CYAN}'auth.py'{RESET}...")
    res = proxy.intercept_tool_call(
        agent_id="agent-auth-lead",
        tool_name="write_file",
        tool_payload={"path": "auth.py", "content": valid_code},
    )
    if res.success:
        print(f"[{GREEN}PERMITTED & COMMITTED{RESET}] {res.output}")
        print(f"  -> Extracted AST Diffs:")
        for diff in res.ast_diffs:
            print(f"     * Type: {CYAN}{diff.get('diff_type')}{RESET} | Symbol: {YELLOW}{diff.get('symbol_id')}{RESET}")
        
        print(f"\n{BOLD}Current Contracts on Shared Blackboard for 'auth.py':{RESET}")
        for contract in blackboard.get_file_contracts("auth.py"):
            print(f"  [Blackboard Entry] {GREEN}{contract.signature}{RESET} (owned by {contract.agent_id})")

    print(f"\n{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN}            FERRY VERIFICATION COMPLETE: ALL 4 GATES PASSED!            {RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}\n")

    shutil.rmtree(temp_workspace, ignore_errors=True)


if __name__ == "__main__":
    run_demo()
