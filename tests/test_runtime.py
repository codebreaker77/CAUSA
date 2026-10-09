import tempfile
from pathlib import Path
import unittest
from packages.astra.runtime import ExecutionRuntime, collect_context
from packages.astra.planner import TaskPlan
from packages.gemini.client import GeminiGenerationResult
from tests.test_scheduler import task


class FakeClient:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def generate_code(self, **kwargs):
        self.calls.append(kwargs)
        code = self.outputs[kwargs["file_path"]]
        return GeminiGenerationResult(success=True, model="fake", response_text=code,
                                      total_tokens=11, cost_usd=0.01)


class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name, "source")
        self.source.mkdir()
        self.runtime = ExecutionRuntime(Path(self.temp.name, "state"))
        self.addCleanup(self.runtime.storage.engine.dispose)

    def plan(self, tasks):
        return TaskPlan(plan_id="test", goal="test", subtasks=tasks)

    def test_success_is_integrated_and_persisted(self):
        client = FakeClient({"a.py": "value=1\n", "b.py": "from a import value\n"})
        output = self.runtime.execute(self.plan([task("a", files=["a.py"]),
            task("b", ["a"], ["b.py"])]), self.source, client)
        self.assertTrue(output["success"], output)
        self.assertTrue(output["applied"])
        self.assertEqual(output["total_tokens"], 22)
        self.assertEqual(Path(self.source, "a.py").read_text(), "value=1\n")
        self.assertIn("a.py", client.calls[1]["existing_repo_files"])
        nodes = self.runtime.storage.get_session_nodes(output["runId"])
        self.assertTrue(any(n.prompt_snapshot and '"inputs"' in (n.metadata or "") for n in nodes))
        self.assertTrue(output["headCommit"])

    def test_failed_validation_does_not_overwrite_source(self):
        Path(self.source, "a.py").write_text("value=1\n")
        client = FakeClient({"a.py": "def broken(:"})
        output = self.runtime.execute(self.plan([task("a", files=["a.py"]),
            task("b", ["a"], ["b.py"])]), self.source, client, max_retries=1)
        self.assertFalse(output["success"])
        self.assertEqual(output["results"][1]["status"], "BLOCKED")
        self.assertEqual(Path(self.source, "a.py").read_text(), "value=1\n")
        self.assertEqual(output["total_tokens"], 22)

    def test_missing_provider_never_completes(self):
        output = self.runtime.execute(self.plan([task("a", files=["a.py"])]), self.source, None)
        self.assertFalse(output["success"])
        self.assertEqual(output["total_tokens"], 0)
        self.assertFalse(Path(self.source, "a.py").exists())

    def test_behavioral_failure_prevents_publication(self):
        client = FakeClient({"test_bad.py": "def test_bad():\n    assert False\n"})
        output = self.runtime.execute(self.plan([task("a", files=["test_bad.py"])]), self.source, client)
        self.assertFalse(output["success"])
        self.assertFalse(Path(self.source, "test_bad.py").exists())

    def test_external_source_changes_are_preserved(self):
        Path(self.source, "a.py").write_text("old=1")
        client = FakeClient({"a.py": "new=2"})
        generate = client.generate_code
        def mutate(**kwargs):
            Path(self.source, "a.py").write_text("external=3")
            return generate(**kwargs)
        client.generate_code = mutate
        output = self.runtime.execute(self.plan([task("a", files=["a.py"])]), self.source, client)
        self.assertFalse(output["success"])
        self.assertEqual(Path(self.source, "a.py").read_text(), "external=3")

    def test_context_keeps_target_tail_and_excludes_secrets(self):
        Path(self.source, "a.py").write_text("x" * 5000 + "TAIL")
        Path(self.source, ".env").write_text("SECRET")
        context = collect_context(self.source, ["a.py"])
        self.assertTrue(context["a.py"].endswith("TAIL"))
        self.assertNotIn(".env", context)
        with self.assertRaises(ValueError):
            collect_context(self.source, ["a.py"], max_chars=10)
