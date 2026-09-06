"""Unit tests for Astra Swarm Supervisor & Lifecycle Engine (Phase 4)."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from packages.astra.supervisor import SwarmSupervisor, SwarmAgentState
from packages.astra.planner import SubTask, ModelTier
from packages.astra.worktree import WorktreeManager
from packages.ferry.proxy import FerryProxy


class TestAstraSupervisor(unittest.TestCase):
    def setUp(self):
        self.test_repo = tempfile.mkdtemp(prefix="causa_sup_test_")
        self._git(["init"], cwd=self.test_repo)
        self._git(["config", "user.name", "Test Supervisor"], cwd=self.test_repo)
        self._git(["config", "user.email", "sup@test.com"], cwd=self.test_repo)

        # Initial commit
        with open(os.path.join(self.test_repo, "README.md"), "w") as f:
            f.write("# Supervised Repo\n")
        self._git(["add", "README.md"], cwd=self.test_repo)
        self._git(["commit", "-m", "initial"], cwd=self.test_repo)

        self.supervisor = SwarmSupervisor(repo_root=self.test_repo)

    def tearDown(self):
        self.supervisor.shutdown_all()
        shutil.rmtree(self.test_repo, ignore_errors=True)

    def _git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.test_repo,
            capture_output=True,
            text=True,
        )

    def test_spawn_and_supervise_agent(self):
        task = SubTask(
            id="t1",
            title="Create Auth Service",
            description="Implement auth module",
            assigned_tier=ModelTier.FAST_CLOUD,
            assigned_model="gemini-1.5-flash",
            target_files=["auth.py"],
        )

        actor = self.supervisor.spawn_agent("agent_auth", task)
        self.assertEqual(actor.state, SwarmAgentState.SANDBOXED)
        self.assertIsNotNone(actor.worktree)
        self.assertTrue(os.path.exists(actor.worktree.worktree_path))

        # Script that writes a file in the sandbox and exits cleanly
        script_code = """
import time
with open('auth.py', 'w') as f:
    f.write('TOKEN = 123\\n')
print('Model: gemini-1.5-flash')
print('Tokens: 5.2k / 100k | Cost: $0.01')
"""
        script_path = os.path.join(actor.worktree.worktree_path, "run.py")
        with open(script_path, "w") as f:
            f.write(script_code)

        launched = self.supervisor.launch_agent_process("agent_auth", f"{sys.executable} run.py")
        self.assertTrue(launched)

        runner = self.supervisor._runners["agent_auth"]
        exit_code = runner.wait(timeout_seconds=5)
        self.assertEqual(exit_code, 0)

        # Verification script (checks that auth.py exists)
        verify_script = f"{sys.executable} -c \"import os; assert os.path.exists('auth.py')\""
        
        # Merge worktree into current branch (HEAD)
        current_branch = self._git(["branch", "--show-current"]).stdout.strip()
        merged = self.supervisor.finalize_agent("agent_auth", verification_command=verify_script, target_branch=current_branch)
        self.assertTrue(merged)
        self.assertEqual(actor.state, SwarmAgentState.MERGED)

        # Confirm file was merged into repo_root
        self.assertTrue(os.path.exists(os.path.join(self.test_repo, "auth.py")))

        # Check telemetry aggregation
        metrics = self.supervisor.get_swarm_metrics()
        self.assertEqual(metrics["total_tokens"], 5200)
        self.assertEqual(metrics["total_cost_usd"], 0.01)


if __name__ == "__main__":
    unittest.main()
