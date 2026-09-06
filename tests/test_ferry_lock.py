"""Unit tests for Ferry Lock & Lease Manager (Phase 1)."""

import time
import unittest
from packages.ferry.lock_manager import LockManager, LeaseLockType


class TestFerryLockManager(unittest.TestCase):
    def setUp(self):
        self.lock_mgr = LockManager(storage=None, default_ttl_seconds=2)

    def test_acquire_and_release_write_lease(self):
        # 1. Agent 1 acquires exclusive write lease
        success, reason, lease = self.lock_mgr.acquire(
            agent_id="agent-auth",
            file_path="src/auth.py",
            lock_type=LeaseLockType.EXCLUSIVE_WRITE,
        )
        self.assertTrue(success)
        self.assertIsNone(reason)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.agent_id, "agent-auth")
        self.assertEqual(lease.lock_state, "acquired")

        # 2. Agent 2 tries to acquire exclusive write lease on same file -> BLOCKED
        success2, reason2, lease2 = self.lock_mgr.acquire(
            agent_id="agent-db",
            file_path="src/auth.py",
            lock_type=LeaseLockType.EXCLUSIVE_WRITE,
        )
        self.assertFalse(success2)
        self.assertIn("currently locked by agent 'agent-auth'", reason2)
        self.assertIsNone(lease2)

        # 3. Agent 1 releases lease
        released = self.lock_mgr.release(agent_id="agent-auth", file_path="src/auth.py")
        self.assertTrue(released)

        # 4. Now Agent 2 can acquire
        success3, reason3, lease3 = self.lock_mgr.acquire(
            agent_id="agent-db",
            file_path="src/auth.py",
            lock_type=LeaseLockType.EXCLUSIVE_WRITE,
        )
        self.assertTrue(success3)
        self.assertIsNone(reason3)
        self.assertIsNotNone(lease3)

    def test_shared_read_leases(self):
        # Two agents can read simultaneously
        s1, _, _ = self.lock_mgr.acquire("agent-1", "routes.py", lock_type=LeaseLockType.SHARED_READ)
        s2, _, _ = self.lock_mgr.acquire("agent-2", "routes.py", lock_type=LeaseLockType.SHARED_READ)
        self.assertTrue(s1)
        self.assertTrue(s2)

        # But a writer is blocked while readers hold it
        sw, reason, _ = self.lock_mgr.acquire("agent-writer", "routes.py", lock_type=LeaseLockType.EXCLUSIVE_WRITE)
        self.assertFalse(sw)
        self.assertIn("currently locked", reason)

    def test_ttl_auto_expiration(self):
        # Acquire with 1 second TTL
        s, _, _ = self.lock_mgr.acquire("agent-crashed", "db.py", ttl_seconds=1)
        self.assertTrue(s)

        # Immediate acquisition by another agent fails
        s_fail, _, _ = self.lock_mgr.acquire("agent-alive", "db.py")
        self.assertFalse(s_fail)

        # Wait for TTL to expire
        time.sleep(1.2)

        # Now acquisition succeeds because lease expired
        s_ok, _, lease = self.lock_mgr.acquire("agent-alive", "db.py")
        self.assertTrue(s_ok)
        self.assertEqual(lease.agent_id, "agent-alive")

    def test_release_all_for_agent(self):
        self.lock_mgr.acquire("agent-x", "file1.py")
        self.lock_mgr.acquire("agent-x", "file2.py")
        self.lock_mgr.acquire("agent-y", "file3.py")

        active = self.lock_mgr.list_active_leases()
        self.assertEqual(len(active), 3)

        # Release all for agent-x
        released = self.lock_mgr.release_all_for_agent("agent-x")
        self.assertEqual(released, 2)

        active_after = self.lock_mgr.list_active_leases()
        self.assertEqual(len(active_after), 1)
        self.assertEqual(active_after[0]["agent_id"], "agent-y")


if __name__ == "__main__":
    unittest.main()
