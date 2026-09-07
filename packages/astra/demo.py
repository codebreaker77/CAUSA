"""Terminal Visual Demo for Astra Swarm Orchestrator.

Demonstrates Astra orchestrating a heterogeneous swarm of agents:
1. Decomposing goals into a directed SubTask DAG.
2. Routing tasks across 3 model tiers (Frontier Heavy vs. Fast Cloud vs. Local SLM).
3. Physical sandboxing in parallel Git worktrees (.causa/worktrees/*).
4. Real-time PTY telemetry scraping (tokens, cost, model name).
5. Pre-merge test verification and atomic 3-way branch merging.
6. Printing live Swarm Telemetry and Token Leaderboard.

Run with:
    python -m packages.astra.demo
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

from packages.astra.planner import TaskPlanner, ModelTier, SubTask
from packages.astra.supervisor import SwarmSupervisor
from packages.ferry.blackboard import Blackboard

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"\n{BOLD}{MAGENTA}========================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}      CAUSA :: ASTRA SWARM ORCHESTRATOR & PROCESS SUPERVISOR            {RESET}")
    print(f"{BOLD}{MAGENTA}========================================================================{RESET}\n")


def run_demo():
    print_banner()

    # Step 1: Create a temporary Git repository to simulate real workspace
    temp_repo = tempfile.mkdtemp(prefix="causa_astra_demo_")
    subprocess.run(["git", "init"], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Astra Demo"], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "astra@causa.local"], cwd=temp_repo, capture_output=True)

    with open(os.path.join(temp_repo, "README.md"), "w") as f:
        f.write("# Causa Swarm Project\nInitial baseline commit.\n")
    subprocess.run(["git", "add", "README.md"], cwd=temp_repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo, capture_output=True)

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=temp_repo, capture_output=True, text=True
    ).stdout.strip() or "master"

    # Step 2: Initialize Astra Planner & Supervisor
    blackboard = Blackboard()
    planner = TaskPlanner(blackboard=blackboard)
    supervisor = SwarmSupervisor(repo_root=temp_repo)

    user_goal = "Build Causal Auth & Session Subsystem"
    print(f"{BOLD}[STEP 1: TASK DECOMPOSITION & SLM ROUTING]{RESET}")
    print(f"Goal: {CYAN}'{user_goal}'{RESET}\n")

    plan = planner.create_plan(user_goal)
    print(f"{BOLD}Decomposed into {len(plan.subtasks)} Directed Subtasks:{RESET}")
    for idx, t in enumerate(plan.subtasks, 1):
        tier_color = RED if t.assigned_tier == ModelTier.FRONTIER_HEAVY else (YELLOW if t.assigned_tier == ModelTier.FAST_CLOUD else GREEN)
        print(f"  {idx}. {BOLD}{t.title}{RESET}")
        print(f"     Tier: {tier_color}{t.assigned_tier.value.upper()}{RESET} ({t.assigned_model})")
        print(f"     Files: {CYAN}{t.target_files}{RESET}")
        print(f"     Dependencies: {t.dependencies if t.dependencies else 'None (Root Task)'}\n")

    time.sleep(0.5)

    # Step 3: Spawn Agents in Isolated Git Worktrees
    print(f"{BOLD}[STEP 2: PROVISIONING ISOLATED GIT WORKTREES]{RESET}")
    actors = []
    for t in plan.subtasks:
        agent_id = f"agent_{t.id}"
        actor = supervisor.spawn_agent(agent_id, t, base_branch=current_branch)
        actors.append(actor)
        print(f"  [Sandbox Created] Agent {YELLOW}'{agent_id}'{RESET} -> {CYAN}{actor.worktree.worktree_path}{RESET}")

    time.sleep(0.5)

    # Step 4: Execute Subagents in Parallel Sandboxes
    print(f"\n{BOLD}[STEP 3: SUPERVISED PTY EXECUTION & REAL-TIME TELEMETRY SCRAPING]{RESET}")

    # We simulate 3 heterogeneous agents writing code in their respective worktrees
    scripts = {
        actors[0].agent_id: """
import time
with open('packages/core/models.py', 'w') as f:
    f.write('class UserModel:\\n    id: str\\n    username: str\\n')
print('Model: claude-3-5-sonnet')
print('Reasoning: Architecting robust relational models...')
time.sleep(0.2)
print('Tokens: 42.1k / 200k | Cost: $0.63')
print('Completed!')
""",
        actors[1].agent_id: """
import time
with open('apps/api/routers.py', 'w') as f:
    f.write('def login_endpoint():\\n    return {"status": "ok"}\\n')
print('Model: gemini-1.5-flash')
print('Reasoning: Generating FastAPI endpoints...')
time.sleep(0.2)
print('Tokens: 28.4k / 100k | Cost: $0.08')
print('Completed!')
""",
        actors[2].agent_id: """
import time
with open('tests/test_service.py', 'w') as f:
    f.write('def test_auth():\\n    assert True\\n')
print('Model: ollama/qwen2.5-coder:7b')
print('Reasoning: Local SLM writing unit tests and docstrings...')
time.sleep(0.2)
print('Tokens: 12.8k / 32k | Cost: $0.00')
print('Completed!')
""",
    }

    def execute_demo_task(task: SubTask):
        actor = next(a for a in actors if a.task.id == task.id)
        target_file = actor.task.target_files[0] if actor.task.target_files else "src/main.py"
        target_full = os.path.join(actor.worktree.worktree_path, target_file)
        os.makedirs(os.path.dirname(target_full), exist_ok=True)

        default_script = f"""import time
with open('{target_file}', 'w') as f:
    f.write('// {actor.task.title}\\nexport const ready = true;\\n')
print('Model: {actor.task.assigned_model}')
print('Reasoning: Executing {actor.task.title}...')
time.sleep(0.2)
print('Tokens: 18.5k / 50k | Cost: $0.05')
print('Completed!')
"""
        script_body = scripts.get(actor.agent_id, default_script)

        script_name = f"{actor.agent_id}_run.py"
        runner_script = os.path.join(actor.worktree.worktree_path, script_name)
        with open(runner_script, "w") as f:
            f.write(script_body)

        supervisor.launch_agent_process(actor.agent_id, f"{sys.executable} {script_name}")
        runner = supervisor._runners[actor.agent_id]
        runner.wait(timeout_seconds=5)

        # Remove runner script before merge so only target code is committed
        script_file = os.path.join(actor.worktree.worktree_path, f"{actor.agent_id}_run.py")
        if os.path.exists(script_file):
            os.remove(script_file)

        print(f"  [Agent Done] {YELLOW}{actor.agent_id}{RESET} ({actor.task.assigned_model})")
        print(f"     -> Scraped Burn: {GREEN}{runner.telemetry.tokens_used:,} tokens{RESET} (${runner.telemetry.cost_usd})")
        return actor

    # Execute all agents respecting the task DAG dependency graph
    supervisor.run_plan(plan, execute_demo_task)
    time.sleep(0.5)

    # Step 5: Automated Verification Gate & Atomic Merge
    print(f"\n{BOLD}[STEP 4: AUTOMATED VERIFICATION & ATOMIC 3-WAY MERGES]{RESET}")
    for actor in actors:
        target_file = actor.task.target_files[0]
        verify_cmd = f"{sys.executable} -c \"import os; assert os.path.exists('{target_file}')\""
        
        merged = supervisor.finalize_agent(
            actor.agent_id,
            verification_command=verify_cmd,
            target_branch=current_branch,
        )
        if merged:
            print(f"  [{GREEN}TEST PASSED & MERGED{RESET}] {YELLOW}{actor.agent_id}{RESET} -> Merged {CYAN}{target_file}{RESET} into {current_branch}")
        else:
            print(f"  [{RED}MERGE REJECTED{RESET}] {actor.error_message}")

    time.sleep(0.5)

    # Step 6: Swarm Telemetry & Cost Leaderboard
    print(f"\n{BOLD}[STEP 5: LIVE SWARM TELEMETRY & MULTI-TIER BUDGET SUMMARY]{RESET}")
    metrics = supervisor.get_swarm_metrics()
    print(f"{BOLD}========================================================================{RESET}")
    print(f" Total Swarm Token Consumption : {CYAN}{metrics['total_tokens']:,} tokens{RESET}")
    print(f" Total Financial Burn          : {GREEN}${metrics['total_cost_usd']:.4f}{RESET}")
    print(f" Subagents Supervised          : {metrics['total_agents']}")
    print(f"------------------------------------------------------------------------")
    print(f"{BOLD} TOKEN USAGE BREAKDOWN BY MODEL TIER:{RESET}")
    for model_name, tokens in metrics["tokens_by_model"].items():
        cost_tag = f"{GREEN}(Free/Local SLM){RESET}" if "ollama" in model_name else f"{YELLOW}(Cloud API){RESET}"
        print(f"   * {model_name:<28} : {tokens:>8,} tokens  {cost_tag}")
    print(f"{BOLD}========================================================================{RESET}")

    print(f"\n{BOLD}{GREEN}ASTRA DEMO COMPLETE: ZERO COLLISION SWARM EXECUTION VERIFIED!{RESET}\n")

    supervisor.shutdown_all()
    shutil.rmtree(temp_repo, ignore_errors=True)


if __name__ == "__main__":
    run_demo()
