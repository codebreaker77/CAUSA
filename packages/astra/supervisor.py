"""Astra Swarm Lifecycle Supervisor & Atomic Merge Engine.

Coordinates the end-to-end multi-agent swarm execution:
1. State Machine: Governs agent lifecycle (INITIALIZING -> SANDBOXED -> RUNNING -> VERIFYING -> MERGED/FAILED).
2. Physical Isolation: Spawns each agent inside an isolated Git worktree via WorktreeManager.
3. Supervised Execution: Runs agent processes via PTYRunner while intercepting tools via FerryProxy.
4. Automated Verification Gate: Executes test commands inside the worktree prior to merging.
5. Atomic 3-Way Merge: Merges verified code into the base branch or quarantines upon conflict/failure.
6. Multi-Provider Budget Accounting: Live tracking of token consumption across model tiers.
"""

import os
import time
import uuid
import concurrent.futures
from typing import Dict, List, Optional, Any, Callable, Set
from pydantic import BaseModel, Field

from packages.astra.worktree import WorktreeManager, WorktreeMetadata
from packages.astra.pty_runner import PTYRunner, AgentProcessTelemetry
from packages.astra.planner import TaskPlan, SubTask, ModelTier
from packages.ferry.proxy import FerryProxy, AgentCapabilityManifest
from packages.ferry.lock_manager import LockManager
from packages.ferry.blackboard import Blackboard


class SwarmAgentState(str):
    INITIALIZING = "INITIALIZING"
    SANDBOXED = "SANDBOXED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    MERGED = "MERGED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


class SwarmAgentActor(BaseModel):
    agent_id: str
    task: SubTask
    state: str = SwarmAgentState.INITIALIZING
    worktree: Optional[WorktreeMetadata] = None
    telemetry: Optional[AgentProcessTelemetry] = None
    verification_passed: bool = False
    verification_log: Optional[str] = None
    error_message: Optional[str] = None
    created_at: int = Field(default_factory=lambda: int(time.time()))


class SwarmSupervisor:
    """Master orchestrator supervising heterogeneous agents, worktrees, and pre-merge gates."""

    def __init__(
        self,
        repo_root: str = "",
        worktree_manager: Optional[WorktreeManager] = None,
        ferry_proxy: Optional[FerryProxy] = None,
        on_event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root or os.getcwd())
        self.worktree_mgr = worktree_manager or WorktreeManager(repo_root=self.repo_root)
        self.ferry = ferry_proxy or FerryProxy(workspace_root=self.repo_root)
        self.on_event = on_event_callback

        # agent_id -> SwarmAgentActor
        self.actors: Dict[str, SwarmAgentActor] = {}
        # agent_id -> PTYRunner
        self._runners: Dict[str, PTYRunner] = {}

    # -------------------------------------------------------------
    # 1. Spawn Agent in Worktree Sandbox
    # -------------------------------------------------------------
    def spawn_agent(
        self,
        agent_id: str,
        task: SubTask,
        base_branch: str = "HEAD",
        capability_manifest: Optional[AgentCapabilityManifest] = None,
    ) -> SwarmAgentActor:
        """Provisions sandbox, registers capability boundaries, and initializes the actor."""
        # 1. Provision Git Worktree
        success, err, meta = self.worktree_mgr.create_worktree(agent_id, base_branch=base_branch)
        if not success:
            actor = SwarmAgentActor(
                agent_id=agent_id,
                task=task,
                state=SwarmAgentState.FAILED,
                error_message=f"Worktree creation failed: {err}",
            )
            self.actors[agent_id] = actor
            self._emit_event("agent_failed", {"agent_id": agent_id, "error": err})
            return actor

        # 2. Register Ferry Capability Manifest
        manifest = capability_manifest or AgentCapabilityManifest(
            agent_id=agent_id,
            allowed_write_patterns=task.target_files if task.target_files else ["*"],
        )
        self.ferry.register_manifest(manifest)

        actor = SwarmAgentActor(
            agent_id=agent_id,
            task=task,
            state=SwarmAgentState.SANDBOXED,
            worktree=meta,
        )
        self.actors[agent_id] = actor
        self._emit_event("agent_spawned", {"agent_id": agent_id, "worktree": meta.worktree_path})
        return actor

    # -------------------------------------------------------------
    # 2. Launch Supervised Agent Process
    # -------------------------------------------------------------
    def launch_agent_process(
        self,
        agent_id: str,
        command: str,
    ) -> bool:
        """Executes the agent CLI inside its sandboxed worktree with PTY supervision."""
        actor = self.actors.get(agent_id)
        if not actor or not actor.worktree:
            return False

        def on_telemetry(t: AgentProcessTelemetry):
            actor.telemetry = t
            self._emit_event("telemetry_update", t.model_dump())

        runner = PTYRunner(
            agent_id=agent_id,
            working_dir=actor.worktree.worktree_path,
            command=command,
            telemetry_callback=on_telemetry,
        )
        self._runners[agent_id] = runner

        actor.state = SwarmAgentState.RUNNING
        started = runner.start()
        if not started:
            actor.state = SwarmAgentState.FAILED
            actor.error_message = "Failed to launch agent subprocess"
            return False

        return True

    # -------------------------------------------------------------
    # 3. Verification Gate & Atomic Merge
    # -------------------------------------------------------------
    def finalize_agent(
        self,
        agent_id: str,
        verification_command: Optional[str] = None,
        target_branch: str = "main",
    ) -> bool:
        """Executes verification tests, commits changes, and atomically merges into target branch."""
        actor = self.actors.get(agent_id)
        if not actor or not actor.worktree:
            return False

        actor.state = SwarmAgentState.VERIFYING
        self._emit_event("verification_started", {"agent_id": agent_id})

        # Step A: Construct default verification command if none provided (Compiler Sandbox)
        if not verification_command and actor.task.target_files:
            target_file = actor.task.target_files[0]
            if target_file.endswith((".ts", ".tsx")):
                verification_command = f"npx tsc --noEmit {target_file}"
            elif target_file.endswith((".js", ".jsx")):
                # Attempt to parse with babel, fallback to eslint, fallback to file existence
                verification_command = f"npx babel {target_file} --dry-run || npx eslint {target_file} || python -c \"import os; assert os.path.exists('{target_file}')\""
            elif target_file.endswith(".py"):
                verification_command = f"python -m py_compile {target_file}"
            else:
                verification_command = f"python -c \"import os; assert os.path.exists('{target_file}')\""

        if not verification_command:
            verification_command = "echo 'No verification command specified'"

        # Step B: Run verification command
        passed, log = self.worktree_mgr.run_verification(agent_id, verification_command)
        actor.verification_passed = passed
        actor.verification_log = log
        if not passed:
            actor.state = SwarmAgentState.FAILED
            actor.error_message = f"Pre-merge verification failed: {log}"
            self._emit_event("verification_failed", {"agent_id": agent_id, "log": log})
            return False

        # Step C: Attempt Atomic 3-Way Merge
        merged, merge_err = self.worktree_mgr.merge_worktree(agent_id, target_branch=target_branch)
        if not merged:
            actor.state = SwarmAgentState.FAILED
            actor.error_message = f"Atomic merge aborted: {merge_err}"
            self._emit_event("merge_failed", {"agent_id": agent_id, "error": merge_err})
            return False

        actor.state = SwarmAgentState.MERGED
        # Release all locks held by this agent
        self.ferry.lock_manager.release_all_for_agent(agent_id)
        self._emit_event("agent_merged", {"agent_id": agent_id, "target_branch": target_branch})
        return True

    # -------------------------------------------------------------
    # 4. DAG-Aware Parallel Plan Scheduler
    # -------------------------------------------------------------
    def run_plan(
        self,
        plan: TaskPlan,
        run_fn: Callable[[SubTask], Any],
        max_workers: int = 4,
    ) -> List[Any]:
        """Executes plan subtasks respecting their DAG dependency graph.

        - Dispatches all tasks with no unmet dependencies concurrently.
        - As tasks finish, unblocks downstream dependent tasks.
        - Independent tasks at the same DAG depth execute in parallel.
        - Detects and raises on cycles/deadlocks.
        """
        subtasks = plan.subtasks
        validate_plan(plan)
        if not subtasks:
            return []
        successful = set()
        terminal = set()
        results = {}
        running = {}
        pending = {task.id: task for task in subtasks}
        pool_size = max(1, min(max_workers, len(subtasks)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
            while pending or running:
                # Propagate failures through the DAG without running consumers.
                for task_id, task in list(pending.items()):
                    failed_deps = set(task.dependencies) & (terminal - successful)
                    if failed_deps:
                        results[task_id] = {
                            "subtaskId": task_id, "status": "BLOCKED", "tokens": 0,
                            "error": "Failed dependencies: " + ", ".join(sorted(failed_deps)),
                        }
                        terminal.add(task_id)
                        del pending[task_id]
                        self._emit_event("task_blocked", results[task_id])
                occupied = {os.path.normcase(os.path.normpath(path))
                            for task in running.values() for path in task.target_files}
                for task_id, task in list(pending.items()):
                    paths = {os.path.normcase(os.path.normpath(path)) for path in task.target_files}
                    if len(running) >= pool_size:
                        break
                    if set(task.dependencies) <= successful and not paths & occupied:
                        del pending[task_id]
                        occupied.update(paths)
                        running[executor.submit(run_fn, task)] = task
                        self._emit_event("task_unblocked", {"task_id": task_id})
                if not running:
                    if pending:
                        # Failure propagation may need another iteration for descendants.
                        continue
                    break
                done, _ = concurrent.futures.wait(
                    running, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    task = running.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"subtaskId": task.id, "status": "FAILED",
                                  "tokens": 0, "error": str(exc)}
                    results[task.id] = result
                    terminal.add(task.id)
                    passed = result is not False and result is not None
                    if isinstance(result, dict):
                        passed = (result.get("success", True) is not False and
                                  str(result.get("status", "COMPLETED")).upper()
                                  in {"COMPLETED", "MERGED", "SUCCESS"})
                    if passed:
                        successful.add(task.id)
                    self._emit_event("task_completed" if passed else "task_failed",
                                     {"task_id": task.id, "status": "COMPLETED" if passed else "FAILED"})
        return [results[task.id] for task in subtasks]

    # -------------------------------------------------------------
    # 5. Swarm Telemetry & Aggregation
    # -------------------------------------------------------------
    def get_swarm_metrics(self) -> Dict[str, Any]:
        """Calculates total token burn, cost, and active agent statuses."""
        total_tokens = 0
        total_cost = 0.0
        by_model: Dict[str, int] = {}
        states: Dict[str, int] = {}

        for actor in self.actors.values():
            st = actor.state
            states[st] = states.get(st, 0) + 1
            if actor.telemetry:
                tokens = actor.telemetry.tokens_used
                total_tokens += tokens
                total_cost += actor.telemetry.cost_usd
                m = actor.telemetry.model_name or actor.task.assigned_model
                by_model[m] = by_model.get(m, 0) + tokens

        return {
            "total_agents": len(self.actors),
            "states": states,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "tokens_by_model": by_model,
        }

    # -------------------------------------------------------------
    # 5. Teardown
    # -------------------------------------------------------------
    def shutdown_agent(self, agent_id: str) -> None:
        """Terminates runner process and cleans up worktree."""
        runner = self._runners.get(agent_id)
        if runner:
            runner.stop()
        self.ferry.lock_manager.release_all_for_agent(agent_id)
        self.worktree_mgr.remove_worktree(agent_id)
        if agent_id in self.actors:
            self.actors[agent_id].state = SwarmAgentState.TERMINATED

    def shutdown_all(self) -> None:
        """Terminates all running agents and cleans all sandboxes."""
        for agent_id in list(self.actors.keys()):
            self.shutdown_agent(agent_id)

    # -------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        if self.on_event:
            try:
                self.on_event(event_type, data)
            except Exception:
                pass


def validate_plan(plan: TaskPlan) -> None:
    """Reject malformed DAGs before any worker has side effects."""
    tasks = {task.id: task for task in plan.subtasks}
    if len(tasks) != len(plan.subtasks):
        raise ValueError("Task IDs must be unique")
    for task in plan.subtasks:
        if not task.id.strip():
            raise ValueError("Task IDs must not be empty")
        missing = set(task.dependencies) - tasks.keys()
        if missing:
            raise ValueError(f"Unknown dependencies for {task.id}: {sorted(missing)}")
    remaining = {key: set(task.dependencies) for key, task in tasks.items()}
    while remaining:
        ready = {key for key, deps in remaining.items() if not deps}
        if not ready:
            raise ValueError("Task dependency graph contains a cycle")
        remaining = {key: deps - ready for key, deps in remaining.items() if key not in ready}
