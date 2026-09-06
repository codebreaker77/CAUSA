"""Unit tests for Astra Git Worktree Sandbox Manager (Phase 1)."""

import os
import shutil
import tempfile
import subprocess
import unittest
from packages.astra.worktree import WorktreeManager


class TestAstraWorktree(unittest.TestCase):
    def setUp(self):
        # Create temporary git repository
        self.test_repo = tempfile.mkdtemp(prefix="causa_test_repo_")
        self._git(["init"], cwd=self.test_repo)
        self._git(["config", "user.name", "Test Agent"], cwd=self.test_repo)
        self._git(["config", "user.email", "agent@test.com"], cwd=self.test_repo)
        
        # Initial commit
        readme_path = os.path.join(self.test_repo, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Initial Project\n")
        self._git(["add", "README.md"], cwd=self.test_repo)
        self._git(["commit", "-m", "initial commit"], cwd=self.test_repo)

        self.mgr = WorktreeManager(repo_root=self.test_repo)

    def tearDown(self):
        shutil.rmtree(self.test_repo, ignore_errors=True)

    def _git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.test_repo,
            capture_output=True,
            text=True,
        )

    def test_create_and_remove_worktree(self):
        # 1. Provision worktree
        success, err, meta = self.mgr.create_worktree(agent_id="worker_auth")
        self.assertTrue(success, f"Creation failed: {err}")
        self.assertIsNotNone(meta)
        self.assertTrue(os.path.exists(meta.worktree_path))

        # 2. Modify a file inside the isolated worktree
        worktree_readme = os.path.join(meta.worktree_path, "README.md")
        with open(worktree_readme, "a") as f:
            f.write("Modified by worker_auth\n")

        # 3. Check diff in worktree
        diff = self.mgr.get_worktree_diff("worker_auth")
        self.assertIn("Modified by worker_auth", diff)

        # Confirm main repo README was NOT modified (isolated sandbox!)
        with open(os.path.join(self.test_repo, "README.md"), "r") as f:
            self.assertNotIn("Modified by worker_auth", f.read())

        # 4. Remove worktree
        removed = self.mgr.remove_worktree("worker_auth")
        self.assertTrue(removed)
        self.assertFalse(os.path.exists(meta.worktree_path))

    def test_verification_gate_in_sandbox(self):
        success, _, meta = self.mgr.create_worktree(agent_id="worker_verify")
        self.assertTrue(success)

        # Create a passing script
        script_path = os.path.join(meta.worktree_path, "verify.py")
        with open(script_path, "w") as f:
            f.write("import sys; sys.exit(0)\n")

        passed, out = self.mgr.run_verification("worker_verify", "python verify.py")
        self.assertTrue(passed)

        # Create a failing script
        with open(script_path, "w") as f:
            f.write("import sys; sys.exit(1)\n")

        failed, out2 = self.mgr.run_verification("worker_verify", "python verify.py")
        self.assertFalse(failed)

        self.mgr.remove_worktree("worker_verify")


if __name__ == "__main__":
    unittest.main()
