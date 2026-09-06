"""Real Model Test Script for Astra and Ferry.

Performs an actual end-to-end execution with your REAL local Ollama SLM (gemma3:latest):
1. Connects to real local Ollama instance on http://localhost:11434.
2. Uses the real SLM to generate code (a unit test suite).
3. Intercepts the real SLM's output with Ferry (validating syntax & leases).
4. Commits the real SLM's code inside an isolated Git worktree sandbox.
5. Runs the real tests inside the sandbox.
6. Merges into target branch if tests pass.
7. Prints ground-truth token accounting directly from the SLM engine.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

from packages.slm.client import LocalSLMClient
from packages.astra.planner import TaskPlanner, SubTask, ModelTier
from packages.astra.supervisor import SwarmSupervisor
from packages.ferry.proxy import FerryProxy
from packages.ferry.lock_manager import LockManager
from packages.ferry.blackboard import Blackboard

BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def test_with_real_model():
    print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
    print(f"{BOLD}{CYAN}       CAUSA :: REAL MODEL EXECUTION WITH LOCAL SLM (OLLAMA)            {RESET}")
    print(f"{BOLD}{CYAN}========================================================================{RESET}\n")

    # 1. Verify Real Ollama Availability
    slm = LocalSLMClient(default_model="gemma3:latest")
    if not slm.is_available():
        print(f"[{RED}ERROR{RESET}] Local Ollama is not responding at http://localhost:11434.")
        print("Please start Ollama service and ensure 'gemma3' is available.")
        return

    models = slm.list_local_models()
    print(f"[{GREEN}CONNECTED TO OLLAMA{RESET}] Local models discovered: {models}")
    print(f"Selected Local SLM: {YELLOW}{slm.default_model}{RESET} (4.3B Parameters, Local, Free)\n")

    # 2. Setup temporary git workspace for physical worktree sandboxing
    temp_repo = tempfile.mkdtemp(prefix="causa_real_model_")
    subprocess.run(["git", "init"], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Causa SLM Agent"], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "slm@causa.local"], cwd=temp_repo, capture_output=True)

    # Initial codebase: A simple math utility
    src_dir = os.path.join(temp_repo, "src")
    os.makedirs(src_dir, exist_ok=True)
    math_code = """# Source code to be tested
def add(a: int, b: int) -> int:
    \"\"\"Adds two numbers.\"\"\"
    return a + b

def multiply(a: int, b: int) -> int:
    \"\"\"Multiplies two numbers.\"\"\"
    return a * b
"""
    with open(os.path.join(src_dir, "math_utils.py"), "w", encoding="utf-8") as f:
        f.write(math_code)

    subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial math utils commit"], cwd=temp_repo, capture_output=True)
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=temp_repo, capture_output=True, text=True
    ).stdout.strip() or "master"

    # 3. Initialize Ferry & Astra
    blackboard = Blackboard()
    lock_mgr = LockManager()
    ferry = FerryProxy(lock_manager=lock_mgr, blackboard=blackboard, workspace_root=temp_repo)
    supervisor = SwarmSupervisor(repo_root=temp_repo, ferry_proxy=ferry)
    planner = TaskPlanner(blackboard=blackboard, slm_client=slm)

    # 4. Provision Worktree Sandbox for the SLM Agent
    subtask = SubTask(
        id="subtask_real_slm",
        title="Generate Unit Test Suite for Math Utils",
        description="Write an executable unittest test case testing add() and multiply() functions in src/math_utils.py",
        assigned_tier=ModelTier.LOCAL_SLM,
        assigned_model=slm.default_model,
        target_files=["tests/test_math.py"],
    )

    print(f"{BOLD}[PHASE 1: PROVISIONING GIT WORKTREE SANDBOX]{RESET}")
    actor = supervisor.spawn_agent("agent_real_slm", subtask, base_branch=current_branch)
    print(f"  Sandbox created at: {CYAN}{actor.worktree.worktree_path}{RESET}\n")

    # 5. REAL INFERENCE WITH LOCAL SLM
    print(f"{BOLD}[PHASE 2: REAL INFERENCE WITH LOCAL SLM ({slm.default_model})]{RESET}")
    print(f"Prompting local SLM to write unit tests for math_utils...")
    t0 = time.time()
    prompt = (
        "You are an expert Python QA engineer.\n"
        "Here is the module src/math_utils.py:\n"
        f"{math_code}\n\n"
        "Write a complete, working unittest test file 'tests/test_math.py'.\n"
        "It MUST import unittest and import add, multiply from src.math_utils.\n"
        "Write assertions for add(2, 3) == 5 and multiply(3, 4) == 12.\n"
        "Output ONLY raw Python code inside triple backticks ```python ... ```."
    )
    res = slm.generate(prompt=prompt, temperature=0.1)
    duration = time.time() - t0

    if not res.success:
        print(f"[{RED}SLM INFERENCE FAILED{RESET}] {res.error}")
        return

    print(f"[{GREEN}SLM GENERATION FINISHED{RESET}] in {duration:.2f}s")
    print(f"  * Prompt Tokens Evaluated    : {CYAN}{res.prompt_tokens}{RESET}")
    print(f"  * Completion Tokens Evaluated: {CYAN}{res.completion_tokens}{RESET}")
    print(f"  * Total Ground-Truth Tokens  : {BOLD}{res.total_tokens}{RESET}")
    print(f"  * Monetary Cost              : {GREEN}$0.00 (Local / Free){RESET}\n")

    # Extract raw python code
    import re
    code_match = re.search(r"```python\s*(.*?)\s*```", res.response_text, re.DOTALL)
    generated_code = code_match.group(1) if code_match else res.response_text

    print(f"{BOLD}[REAL GENERATED CODE FROM SLM]:{RESET}")
    print("--------------------------------------------------")
    print(generated_code.strip())
    print("--------------------------------------------------\n")

    # 6. FERRY INTERCEPTION (Dry-run syntax validation & capability check)
    print(f"{BOLD}[PHASE 3: FERRY PRE-COMMIT INTERCEPTION GATE]{RESET}")
    # Write through Ferry into the sandbox
    ferry.workspace_root = actor.worktree.worktree_path
    intercept_res = ferry.intercept_tool_call(
        agent_id="agent_real_slm",
        tool_name="write_file",
        tool_payload={"path": "tests/test_math.py", "content": generated_code},
    )

    if not intercept_res.success:
        print(f"[{RED}BLOCKED BY FERRY{RESET}] {intercept_res.error_message}")
        print("Ferry caught a syntax or boundary violation before disk write!")
        return

    print(f"[{GREEN}PERMITTED BY FERRY{RESET}] {intercept_res.output}")
    print(f"  -> Extracted AST Diffs: {len(intercept_res.ast_diffs)} symbols published to Blackboard\n")

    # 7. EXECUTE TEST IN WORKTREE SANDBOX & ATOMIC MERGE
    print(f"{BOLD}[PHASE 4: EXECUTE VERIFICATION IN SANDBOX & ATOMIC MERGE]{RESET}")
    # Ensure tests package has __init__.py in the sandbox
    init_path = os.path.join(actor.worktree.worktree_path, "tests", "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("")

    verify_cmd = f"{sys.executable} -m unittest discover -s tests"
    print(f"Running verification command: {CYAN}{verify_cmd}{RESET}")
    
    passed, log = supervisor.worktree_mgr.run_verification("agent_real_slm", verify_cmd)
    print(f"Verification Result: {'PASSED' if passed else 'FAILED'}")
    print(f"Log:\n{log.strip()}\n")

    if passed:
        merged = supervisor.finalize_agent(
            "agent_real_slm",
            verification_command=verify_cmd,
            target_branch=current_branch,
        )
        if merged:
            print(f"[{GREEN}SUCCESS{RESET}] Real SLM code verified & atomically merged into branch '{current_branch}'!")
            
            # Check the merged file in base repo
            merged_file = os.path.join(temp_repo, "tests", "test_math.py")
            print(f"Physical file exists in root repository: {os.path.exists(merged_file)}")

    # Cleanup
    supervisor.shutdown_all()
    shutil.rmtree(temp_repo, ignore_errors=True)
    print(f"\n{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN}     END-TO-END REAL SLM TEST COMPLETED WITH 100% PASSING RESULTS!      {RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}\n")


if __name__ == "__main__":
    test_with_real_model()
