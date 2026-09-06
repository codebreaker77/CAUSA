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
from typing import Dict, List, Optional, Any, Callable
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

        # Step A: Run verification command if requested
        if verification_command:
            passed, log = self.worktree_mgr.run_verification(agent_id, verification_command)
            actor.verification_passed = passed
            actor.verification_log = log
            if not passed:
                actor.state = SwarmAgentState.FAILED
                actor.error_message = f"Pre-merge verification failed: {log}"
                self._emit_event("verification_failed", {"agent_id": agent_id, "log": log})
                return False

        # Step B: Attempt Atomic 3-Way Merge
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
    # 4. Swarm Telemetry & Aggregation
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
