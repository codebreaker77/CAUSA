import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from tests.test_runtime import FakeClient


class TestExecutionAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {"CAUSA_WORKSPACE_DIR": self.temp.name, "GEMINI_API_KEY": ""}), \
                patch("dotenv.load_dotenv", return_value=False):
            if "apps.api.main" in sys.modules:
                self.api = importlib.reload(sys.modules["apps.api.main"])
            else:
                self.api = importlib.import_module("apps.api.main")
        self.addCleanup(self.api.runtime.storage.engine.dispose)
        self.client = TestClient(self.api.app)

    def execute(self, filename="a.py", **extra):
        return self.client.post("/api/execute", json={"prompt": "test", "subtasks": [
            {"id": "a", "nodeTitle": "A", "prompt": "test", "targetFiles": [filename]}], **extra})

    def test_missing_provider_reports_failure_and_zero_usage(self):
        self.api.gemini_client = None
        response = self.execute()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["total_tokens"], 0)

    def test_path_escape_rejected_before_generation(self):
        self.api.gemini_client = FakeClient({})
        self.assertEqual(self.execute("../a.py").status_code, 400)
        self.assertEqual(self.execute(project_subdir="../escape").status_code, 400)
        self.assertEqual(self.api.gemini_client.calls, [])

    def test_persistent_graph_and_isolated_fork(self):
        self.api.gemini_client = FakeClient({"a.py": "value=1\n"})
        data = self.execute().json()
        self.assertTrue(data["success"], data)
        graph = self.client.get(f'/api/runs/{data["runId"]}/dag').json()
        self.assertTrue(graph["nodes"])
        self.assertTrue(graph["edges"])
        self.api.gemini_client = FakeClient({"a.py": "value=2\n"})
        fork = self.client.post("/api/fork", json={
            "parent_node_id": data["results"][0]["causalNodeId"],
            "fork_prompt": "Change value", "target_files": ["a.py"]}).json()
        self.assertTrue(fork["success"], fork)
        self.assertFalse(fork["applied"])
        self.assertEqual(Path(self.temp.name, "a.py").read_text(), "value=1\n")
        self.assertEqual(Path(fork["workspace"], "a.py").read_text(), "value=2\n")
        self.assertEqual(self.client.get("/api/telemetry").json()["metrics"]["total_tokens"], 11)

    def test_demo_node_cannot_be_forked_as_checkpoint(self):
        self.assertEqual(self.client.post("/api/fork", json={"parent_node_id": "s6",
            "fork_prompt": "test"}).status_code, 404)
