"""Unit tests for Ferry AST Diff & Syntax Inspector (Phase 2)."""

import unittest
from packages.ferry.ast_diff import ASTInspector


class TestFerryASTDiff(unittest.TestCase):
    def test_syntax_validation_pass(self):
        valid_code = """
def calculate_metrics(items: list[int]) -> int:
    return sum(items)
"""
        res = ASTInspector.validate_syntax(valid_code, file_path="metrics.py")
        self.assertTrue(res.is_valid)
        self.assertIsNone(res.error_message)

    def test_syntax_validation_fail(self):
        # Missing closing parenthesis and bad syntax
        broken_code = """
def broken_fn(a, b:
    return a + b
"""
        res = ASTInspector.validate_syntax(broken_code, file_path="broken.py")
        self.assertFalse(res.is_valid)
        self.assertIn("SyntaxError", res.error_message)
        self.assertIn(res.line_number, [2, 3])

    def test_symbol_extraction(self):
        code = """
class AuthService:
    def verify_token(self, token: str) -> bool:
        return True

async def fetch_user(user_id: int) -> dict:
    return {"id": user_id}
"""
        symbols = ASTInspector.extract_symbols(code, file_path="auth.py")
        self.assertIn("class:AuthService", symbols)
        self.assertIn("class:AuthService.method:verify_token", symbols)
        self.assertIn("func:fetch_user", symbols)

        fetch_fn = symbols["func:fetch_user"]
        self.assertEqual(fetch_fn.kind, "async_function")
        self.assertEqual(fetch_fn.signature, "async def fetch_user(user_id: int) -> dict")

    def test_ast_diff_signature_changed(self):
        before = """
def login(username: str) -> bool:
    return True
"""
        # Changed signature: added password parameter
        after = """
def login(username: str, password: str) -> bool:
    return True
"""
        diffs = ASTInspector.compute_ast_diffs(before, after, file_path="auth.py")
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].diff_type, "signature_changed")
        self.assertEqual(diffs[0].symbol_id, "func:login")
        self.assertEqual(diffs[0].before_signature, "def login(username: str) -> bool")
        self.assertEqual(diffs[0].after_signature, "def login(username: str, password: str) -> bool")

    def test_ast_diff_added_and_deleted_export(self):
        before = """
def old_function():
    pass
"""
        after = """
def new_function():
    pass
"""
        diffs = ASTInspector.compute_ast_diffs(before, after, file_path="exports.py")
        self.assertEqual(len(diffs), 2)
        diff_types = {d.diff_type for d in diffs}
        self.assertIn("deleted_export", diff_types)
        self.assertIn("added_export", diff_types)

    def test_ast_diff_body_changed_only(self):
        before = """
def compute(x: int) -> int:
    return x * 2
"""
        # Signature is identical, only body calculation changed
        after = """
def compute(x: int) -> int:
    # Optimized calculation
    return x << 1
"""
        diffs = ASTInspector.compute_ast_diffs(before, after, file_path="calc.py")
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].diff_type, "body_changed")


if __name__ == "__main__":
    unittest.main()
