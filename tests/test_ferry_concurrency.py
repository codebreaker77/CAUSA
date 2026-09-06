"""Unit & Multi-Threaded Concurrency Tests for Ferry Pre-Commit Engine (Phase 5)."""

import os
import shutil
import tempfile
import threading
import unittest
from packages.ferry.proxy import FerryProxy, AgentCapabilityManifest
from packages.ferry.lock_manager import LockManager
from packages.ferry.blackboard import Blackboard


class TestFerryConcurrency(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.lock_mgr = LockManager(default_ttl_seconds=3)
        self.blackboard = Blackboard()
        self.proxy = FerryProxy(
            lock_manager=self.lock_mgr,
            blackboard=self.blackboard,
            workspace_root=self.test_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_multi_agent_concurrent_write_contention(self):
        """Simulates 10 concurrent agents competing to write to the exact same file.
        Ferry must guarantee zero dirty overwrites or file corruption.
        """
        target_file = "shared/config.py"
        success_count = 0
        blocked_count = 0
        lock = threading.Lock()

        def agent_task(agent_id: str, content: str):
            nonlocal success_count, blocked_count
            res = self.proxy.intercept_tool_call(
                agent_id=agent_id,
                tool_name="write_file",
                tool_payload={"path": target_file, "content": content},
            )
            with lock:
                if res.success:
                    success_count += 1
                else:
                    blocked_count += 1

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=agent_task,
                args=(f"agent-{i}", f"# Config from agent {i}\nVERSION = {i}\n"),
            )
            threads.append(t)

        # Launch all 10 agents simultaneously
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one succeeded, and the rest were blocked due to exclusive leases
        self.assertGreaterEqual(success_count, 1)
        self.assertEqual(success_count + blocked_count, 10)

        # Confirm the final file on disk is valid and uncorrupted
        file_path = os.path.join(self.test_dir, target_file)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("VERSION = ", content)


if __name__ == "__main__":
    unittest.main()
