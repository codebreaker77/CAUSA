import unittest
from packages.ferry.blackboard import Blackboard
from packages.ferry.ast_diff import ASTInspector


class TestContractRevisions(unittest.TestCase):
    def test_equal_names_do_not_collide_and_deleted_exports_disappear(self):
        board = Blackboard()
        symbols = ASTInspector.extract_symbols("def same():\n    pass\n", "a.py")
        board.publish_symbols(symbols, "a.py", "a")
        board.publish_symbols(symbols, "b.py", "b")
        self.assertEqual(len(board.get_all_contracts()), 2)
        board.publish_symbols({}, "a.py", "a")
        self.assertEqual(board.get_file_contracts("a.py"), [])
        self.assertEqual(len(board.get_file_contracts("b.py")), 1)
