import threading
import time
import unittest

from packages.astra.planner import ModelTier, SubTask, TaskPlan
from packages.astra.supervisor import SwarmSupervisor


def task(key, deps=(), files=()):
    return SubTask(id=key, title=key, description=key,
                   assigned_tier=ModelTier.FAST_CLOUD, assigned_model="fake",
                   dependencies=list(deps), target_files=list(files))


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.supervisor = SwarmSupervisor.__new__(SwarmSupervisor)
        self.supervisor.on_event = None

    def run_tasks(self, tasks, worker):
        return self.supervisor.run_plan(TaskPlan(plan_id="test", goal="test", subtasks=tasks), worker, 2)

    def test_failed_dependencies_block_transitively(self):
        seen = []
        def worker(t):
            seen.append(t.id)
            return {"status": "FAILED" if t.id == "a" else "COMPLETED"}
        results = self.run_tasks([task("a"), task("b", ["a"]), task("c", ["b"]), task("d")], worker)
        self.assertEqual([r["status"] for r in results], ["FAILED", "BLOCKED", "BLOCKED", "COMPLETED"])
        self.assertEqual(set(seen), {"a", "d"})

    def test_exception_blocks_dependents(self):
        def worker(t):
            raise RuntimeError("generation failed")
        results = self.run_tasks([task("a"), task("b", ["a"])], worker)
        self.assertEqual(results[1]["status"], "BLOCKED")

    def test_invalid_plans_have_no_side_effects(self):
        for tasks in ([task("a"), task("a")], [task("a", ["missing"])],
                      [task("a", ["b"]), task("b", ["a"])], [task("a", ["a"])]):
            with self.assertRaises(ValueError):
                self.run_tasks(tasks, lambda t: self.fail("Worker must not run"))

    def test_overlapping_files_are_serialized(self):
        active = set()
        lock = threading.Lock()
        def worker(t):
            with lock:
                self.assertFalse(active)
                active.add(t.id)
            time.sleep(0.02)
            with lock:
                active.remove(t.id)
            return {"status": "COMPLETED"}
        results = self.run_tasks([task("a", files=["a.py"]), task("b", files=["./a.py"])], worker)
        self.assertTrue(all(r["status"] == "COMPLETED" for r in results))
