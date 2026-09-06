"""Unit tests for Ferry Transparent Proxy & Pre-Commit Gateway (Phase 4)."""

import os
import shutil
import tempfile
import unittest
from packages.ferry.proxy import FerryProxy, AgentCapabilityManifest
from packages.ferry.lock_manager import LockManager
from packages.ferry.blackboard import Blackboard


class TestFerryProxy(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.lock_mgr = LockManager(default_ttl_seconds=5)
        self.blackboard = Blackboard()
        self.proxy = FerryProxy(
            lock_manager=self.lock_mgr,
            blackboard=self.blackboard,
            workspace_root=self.test_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_file_success_and_diff_extraction(self):
        code_content = """
def authenticate_user(username: str) -> bool:
    return True
"""
        res = self.proxy.intercept_tool_call(
            agent_id="agent-auth",
            tool_name="write_file",
            tool_payload={"path": "auth.py", "content": code_content},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.decision, "allowed")

        # Verify physical disk write happened
        file_path = os.path.join(self.test_dir, "auth.py")
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), code_content)

        # Verify signature was published to blackboard
        symbols = self.blackboard.get_file_contracts("auth.py")
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0].name, "authenticate_user")

    def test_write_file_syntax_error_rejected(self):
        broken_code = """
def broken_syntax(a, b:
    return a
"""
        res = self.proxy.intercept_tool_call(
            agent_id="agent-bad",
            tool_name="write_file",
            tool_payload={"path": "broken.py", "content": broken_code},
        )
        self.assertFalse(res.success)
        self.assertEqual(res.decision, "blocked")
        self.assertIn("AST Syntax Validation Rejected", res.error_message)

        # Ensure disk file was NOT created
        file_path = os.path.join(self.test_dir, "broken.py")
        self.assertFalse(os.path.exists(file_path))

    def test_capability_manifest_boundary_rejection(self):
        # Scope agent strictly to frontend/**
        manifest = AgentCapabilityManifest(
            agent_id="agent-frontend",
            allowed_write_patterns=["frontend/*"],
            disallowed_write_patterns=["*.env"],
        )
        self.proxy.register_manifest(manifest)

        # Attempt to write to backend/db.py -> Rejected
        res = self.proxy.intercept_tool_call(
            agent_id="agent-frontend",
            tool_name="write_file",
            tool_payload={"path": "backend/db.py", "content": "x = 1\n"},
        )
        self.assertFalse(res.success)
        self.assertEqual(res.decision, "blocked")
        self.assertIn("Security Violation", res.error_message)

        # Attempt to write to frontend/app.py -> Allowed
        res_allowed = self.proxy.intercept_tool_call(
            agent_id="agent-frontend",
            tool_name="write_file",
            tool_payload={"path": "frontend/app.py", "content": "x = 1\n"},
        )
        self.assertTrue(res_allowed.success)

    def test_dangerous_command_blocked(self):
        res = self.proxy.intercept_tool_call(
            agent_id="agent-rogue",
            tool_name="execute_command",
            tool_payload={"command": "rm -rf /"},
        )
        self.assertFalse(res.success)
        self.assertEqual(res.decision, "blocked")
        self.assertIn("Security Violation: Rejected dangerous command", res.error_message)


if __name__ == "__main__":
    unittest.main()
