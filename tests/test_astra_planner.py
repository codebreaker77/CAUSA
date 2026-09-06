"""Unit tests for Astra Task Decomposition & Model Router (Phase 3)."""

import unittest
from packages.astra.planner import TaskPlanner, ModelTier
from packages.ferry.blackboard import Blackboard


class TestAstraPlanner(unittest.TestCase):
    def setUp(self):
        self.blackboard = Blackboard()
        self.planner = TaskPlanner(blackboard=self.blackboard)

    def test_model_tier_routing(self):
        # 1. Complex architecture -> Frontier Heavy
        tier, model = self.planner.route_task_to_tier(
            "Architect Causal DAG Substrate",
            "Resolve concurrency and distributed race conditions",
        )
        self.assertEqual(tier, ModelTier.FRONTIER_HEAVY)
        self.assertEqual(model, "claude-3-5-sonnet")

        # 2. Standard API CRUD -> Fast Cloud
        tier2, model2 = self.planner.route_task_to_tier(
            "User Profile Endpoints",
            "Implement standard REST endpoints for user profiles",
        )
        self.assertEqual(tier2, ModelTier.FAST_CLOUD)
        self.assertEqual(model2, "gemini-1.5-flash")

        # 3. Unit Tests -> Local SLM (0 cost)
        tier3, model3 = self.planner.route_task_to_tier(
            "Unit Tests",
            "Write pytest unit tests and docstring documentation",
        )
        self.assertEqual(tier3, ModelTier.LOCAL_SLM)
        self.assertEqual(model3, "ollama/qwen2.5-coder:7b")

    def test_ast_context_synthesis(self):
        # Populate blackboard with an interface
        self.blackboard.publish(
            symbol_id="func:login",
            name="login",
            signature="def login(username: str, token: str) -> bool",
            file_path="src/auth.py",
            agent_id="agent-auth",
        )

        ctx = self.planner.synthesize_ast_context(["src/auth.py"])
        self.assertIn("Synthesized AST Interface Contracts", ctx)
        self.assertIn("def login(username: str, token: str) -> bool", ctx)

    def test_plan_generation_and_dag_ordering(self):
        plan = self.planner.create_plan("Build Authentication System")
        self.assertEqual(len(plan.subtasks), 3)

        # Confirm 3 tiers are represented
        tiers = {t.assigned_tier for t in plan.subtasks}
        self.assertIn(ModelTier.FRONTIER_HEAVY, tiers)
        self.assertIn(ModelTier.FAST_CLOUD, tiers)
        self.assertIn(ModelTier.LOCAL_SLM, tiers)

        # Confirm dependency ordering: Task 2 depends on Task 1, Task 3 depends on Task 2
        t1, t2, t3 = plan.subtasks[0], plan.subtasks[1], plan.subtasks[2]
        self.assertEqual(t1.dependencies, [])
        self.assertEqual(t2.dependencies, [t1.id])
        self.assertEqual(t3.dependencies, [t2.id])


if __name__ == "__main__":
    unittest.main()
