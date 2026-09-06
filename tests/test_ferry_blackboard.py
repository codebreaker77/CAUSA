"""Unit tests for Ferry Blackboard (Phase 3)."""

import unittest
from packages.ferry.blackboard import Blackboard
from packages.ferry.ast_diff import ASTInspector


class TestFerryBlackboard(unittest.TestCase):
    def setUp(self):
        self.bb = Blackboard(storage=None)

    def test_publish_and_retrieve_contract(self):
        entry = self.bb.publish(
            symbol_id="func:authenticate",
            name="authenticate",
            signature="def authenticate(username: str, token: str) -> bool",
            file_path="src/auth.py",
            agent_id="agent-auth-1",
        )
        self.assertEqual(entry.symbol_id, "func:authenticate")

        # Query by symbol
        retrieved = self.bb.get_symbol("func:authenticate")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "authenticate")
        self.assertEqual(retrieved.agent_id, "agent-auth-1")

    def test_bulk_publish_from_ast_symbols(self):
        code = """
def generate_jwt(user_id: int) -> str:
    return "token"

def revoke_jwt(token: str) -> bool:
    return True
"""
        symbols = ASTInspector.extract_symbols(code, file_path="jwt.py")
        published = self.bb.publish_symbols(symbols, file_path="jwt.py", agent_id="agent-jwt")
        self.assertEqual(len(published), 2)

        file_contracts = self.bb.get_file_contracts("jwt.py")
        self.assertEqual(len(file_contracts), 2)
        names = {c.name for c in file_contracts}
        self.assertIn("generate_jwt", names)
        self.assertIn("revoke_jwt", names)

    def test_symbol_history_tracking(self):
        # Version 1
        self.bb.publish(
            symbol_id="func:calc",
            name="calc",
            signature="def calc(x: int) -> int",
            file_path="calc.py",
            agent_id="agent-1",
        )
        # Version 2
        self.bb.publish(
            symbol_id="func:calc",
            name="calc",
            signature="def calc(x: int, y: int = 0) -> int",
            file_path="calc.py",
            agent_id="agent-2",
        )

        current = self.bb.get_symbol("func:calc")
        self.assertEqual(current.agent_id, "agent-2")
        self.assertIn("y: int = 0", current.signature)

        history = self.bb.get_symbol_history("func:calc")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].agent_id, "agent-1")
        self.assertEqual(history[1].agent_id, "agent-2")


if __name__ == "__main__":
    unittest.main()
