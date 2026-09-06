"""Astra Task Decomposition, AST Context Synthesis & SLM Model Router.

Breaks high-level user directives into structured subtask dependency graphs (DAG)
and intelligently routes tasks across model tiers:
1. Frontier Heavy (Claude 3.5 Sonnet / GPT-4o) -> Complex logic, architecture, refactors.
2. Fast Cloud (Gemini 1.5 Flash / Claude Haiku) -> Standard endpoints, database schemas.
3. Local SLM (Ollama Qwen2.5-Coder / Phi-3) -> Unit tests, docs, formatting, typed stubs (0 cost).

Also performs AST Context Synthesis: injects minimal interface skeletons from
Ferry's Blackboard instead of entire source files.
"""

import json
import os
import re
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from pydantic import BaseModel, Field

from packages.ferry.blackboard import Blackboard, BlackboardEntry


class ModelTier(str, Enum):
    FRONTIER_HEAVY = "frontier_heavy"  # Claude 3.5 Sonnet, GPT-4o
    FAST_CLOUD = "fast_cloud"          # Gemini 1.5 Flash, Claude Haiku
    LOCAL_SLM = "local_slm"            # Ollama Qwen2.5-Coder:7b, Phi-3


class SubTask(BaseModel):
    id: str
    title: str
    description: str
    assigned_tier: ModelTier
    assigned_model: str
    target_files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)  # IDs of predecessor tasks
    synthesized_context: str = ""
    status: str = "pending"  # "pending", "ready", "running", "completed", "failed"


class TaskPlan(BaseModel):
    plan_id: str
    goal: str
    subtasks: List[SubTask]
    dependency_graph: Dict[str, List[str]] = Field(default_factory=dict)  # task_id -> list of dependent task_ids


class TaskPlanner:
    """Decomposes goals, routes to optimal model tiers, and synthesizes AST context."""

    MODEL_MAPPINGS = {
        ModelTier.FRONTIER_HEAVY: "claude-3-5-sonnet",
        ModelTier.FAST_CLOUD: "gemini-1.5-flash",
        ModelTier.LOCAL_SLM: "ollama/qwen2.5-coder:7b",
    }

    def __init__(
        self,
        blackboard: Optional[Blackboard] = None,
        ollama_client: Optional[Any] = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.ollama = ollama_client

    # -------------------------------------------------------------
    # 1. Model Tier Routing Logic (Rule-based + SLM fallback)
    # -------------------------------------------------------------
    @classmethod
    def route_task_to_tier(cls, task_title: str, task_desc: str) -> Tuple[ModelTier, str]:
        """Classifies task complexity and assigns the optimal model tier.
        
        Saves tokens by delegating unit tests, formatting, and stubs to local SLM.
        """
        text = f"{task_title} {task_desc}".lower()

        # Tier 3: Local SLM (Zero cost operations)
        slm_keywords = [
            "unit test", "write tests", "test suite", "documentation", "docstring",
            "formatting", "type annotations", "skeleton", "stub", "comment",
        ]
        if any(k in text for k in slm_keywords):
            return ModelTier.LOCAL_SLM, cls.MODEL_MAPPINGS[ModelTier.LOCAL_SLM]

        # Tier 1: Frontier Heavy (High cognitive load)
        frontier_keywords = [
            "architect", "concurrency", "distributed", "security", "cryptography",
            "refactor core", "algorithm", "race condition", "time-travel", "deadlock",
        ]
        if any(k in text for k in frontier_keywords):
            return ModelTier.FRONTIER_HEAVY, cls.MODEL_MAPPINGS[ModelTier.FRONTIER_HEAVY]

        # Tier 2: Fast Cloud (Standard CRUD, endpoints, database migrations)
        return ModelTier.FAST_CLOUD, cls.MODEL_MAPPINGS[ModelTier.FAST_CLOUD]

    # -------------------------------------------------------------
    # 2. AST Context Synthesis
    # -------------------------------------------------------------
    def synthesize_ast_context(self, target_files: List[str]) -> str:
        """Extracts exported symbol signatures from the Blackboard for relevant files.
        
        Instead of injecting 10,000 lines of implementation code into the agent's
        context window, we inject a dense 100-line skeletal interface contract.
        """
        if not target_files:
            return ""

        context_lines = ["### Synthesized AST Interface Contracts (from Causa Blackboard):"]
        found_any = False

        for file_path in target_files:
            contracts = self.blackboard.get_file_contracts(file_path)
            if contracts:
                found_any = True
                context_lines.append(f"\n# File: {file_path}")
                for entry in contracts:
                    context_lines.append(f"  {entry.signature}")

        if not found_any:
            return ""

        return "\n".join(context_lines)

    # -------------------------------------------------------------
    # 3. High-Level Plan Generation
    # -------------------------------------------------------------
    def create_plan(
        self,
        goal: str,
        custom_subtasks: Optional[List[Dict[str, Any]]] = None,
    ) -> TaskPlan:
        """Decomposes a goal into an ordered SubTask DAG.
        
        Can accept structured definitions or infer subtasks heuristically.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # If subtasks are provided explicitly
        if custom_subtasks:
            subtasks = []
            for item in custom_subtasks:
                tier, model = self.route_task_to_tier(item.get("title", ""), item.get("description", ""))
                task_id = item.get("id", f"task_{uuid.uuid4().hex[:6]}")
                files = item.get("target_files", [])
                ast_ctx = self.synthesize_ast_context(files)

                subtasks.append(
                    SubTask(
                        id=task_id,
                        title=item.get("title", "Untitled Task"),
                        description=item.get("description", ""),
                        assigned_tier=tier,
                        assigned_model=model,
                        target_files=files,
                        dependencies=item.get("dependencies", []),
                        synthesized_context=ast_ctx,
                    )
                )
            return TaskPlan(
                plan_id=plan_id,
                goal=goal,
                subtasks=subtasks,
                dependency_graph=self._build_dep_graph(subtasks),
            )

        # Default intelligent decomposition heuristic for demo/pipeline
        subtasks = self._heuristic_decomposition(goal)
        return TaskPlan(
            plan_id=plan_id,
            goal=goal,
            subtasks=subtasks,
            dependency_graph=self._build_dep_graph(subtasks),
        )

    # -------------------------------------------------------------
    # Internal Heuristics
    # -------------------------------------------------------------
    def _heuristic_decomposition(self, goal: str) -> List[SubTask]:
        """Automatically splits a goal into standard layered architecture tasks."""
        t1_id = f"task_{uuid.uuid4().hex[:6]}"
        t2_id = f"task_{uuid.uuid4().hex[:6]}"
        t3_id = f"task_{uuid.uuid4().hex[:6]}"

        tier1, model1 = self.route_task_to_tier("Core Architecture & Types", f"Define types for: {goal}")
        tier2, model2 = self.route_task_to_tier("API Endpoints & Implementation", f"Implement logic for: {goal}")
        tier3, model3 = self.route_task_to_tier("Unit Tests & Verification", f"Write unit tests for: {goal}")

        return [
            SubTask(
                id=t1_id,
                title="Core Data Models & Interfaces",
                description=f"Define interfaces and schemas for {goal}",
                assigned_tier=tier1,
                assigned_model=model1,
                target_files=["packages/core/models.py"],
                dependencies=[],
            ),
            SubTask(
                id=t2_id,
                title="Service Logic & Endpoints",
                description=f"Implement business logic for {goal}",
                assigned_tier=tier2,
                assigned_model=model2,
                target_files=["apps/api/routers.py"],
                dependencies=[t1_id],
            ),
            SubTask(
                id=t3_id,
                title="Unit Tests & Edge Cases (Local SLM)",
                description=f"Write comprehensive test suite for {goal}",
                assigned_tier=tier3,
                assigned_model=model3,
                target_files=["tests/test_service.py"],
                dependencies=[t2_id],
            ),
        ]

    def _build_dep_graph(self, subtasks: List[SubTask]) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {t.id: [] for t in subtasks}
        for t in subtasks:
            for dep in t.dependencies:
                if dep in graph:
                    graph[dep].append(t.id)
        return graph
