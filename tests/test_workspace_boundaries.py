import tempfile
from pathlib import Path
import unittest

from packages.paths import workspace_path
from packages.ferry.proxy import FerryProxy
from packages.ferry.lock_manager import LockManager


class TestBoundaries(unittest.TestCase):
    def test_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as root:
            for path in ("../x.py", "src/../../x.py", "C:/x.py", "/tmp/x.py", "\\\\host\\share\\x"):
                with self.assertRaises(ValueError):
                    workspace_path(root, path)
                proxy = FerryProxy(workspace_root=root)
                result = proxy.intercept_tool_call("a", "write_file", {"path": path, "content": "x=1"})
                self.assertFalse(result.success)
            self.assertEqual(workspace_path(root, "./src/x.py"), Path(root).resolve() / "src/x.py")

    def test_private_paths_and_conflicted_reads(self):
        with tempfile.TemporaryDirectory() as root:
            proxy = FerryProxy(workspace_root=root)
            Path(root, "x.py").write_text("x=1")
            proxy.lock_manager.acquire("writer", "x.py")
            result = proxy.intercept_tool_call("reader", "read_file", {"path": "x.py"})
            self.assertFalse(result.success)
            self.assertEqual(proxy.lock_manager.get_lease("x.py")["agent_id"], "writer")
            for path in (".env", ".git/config", ".causa/state.py"):
                self.assertFalse(proxy.intercept_tool_call("a", "write_file", {"path": path, "content": "x=1"}).success)

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            try:
                Path(root, "link").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Host does not permit symlinks")
            with self.assertRaises(ValueError):
                workspace_path(root, "link/x.py")

    def test_read_upgrade_and_release_ownership(self):
        locks = LockManager()
        locks.acquire("a", "x.py", "READ")
        locks.acquire("b", "x.py", "READ")
        self.assertFalse(locks.acquire("a", "x.py", "WRITE")[0])
        self.assertFalse(locks.release("outsider", "x.py"))
        self.assertTrue(locks.release("b", "x.py"))
        self.assertTrue(locks.acquire("a", "x.py", "WRITE")[0])
        self.assertEqual(locks.get_lease("x.py")["lock_type"], "WRITE")
        self.assertFalse(locks.acquire("b", "./x.py", "READ")[0])

