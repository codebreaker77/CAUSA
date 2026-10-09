import tempfile
from pathlib import Path
import unittest

from packages.astra.verification import verify_files, execution_env
from unittest.mock import patch


class TestVerification(unittest.TestCase):
    def test_invalid_sources_fail(self):
        with tempfile.TemporaryDirectory() as root:
            for filename, source in (("x.py", "def x(:"), ("x.json", "{bad}"),
                                     ("x.jsx", "export const X = <div>")):
                Path(root, filename).write_text(source)
                result = verify_files(root, [filename], run_tests=False)
                self.assertFalse(result.passed, filename)

    def test_valid_js_and_python(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "x.jsx").write_text("export const X = () => <div>Hello</div>;")
            Path(root, "x.py").write_text("x = 1")
            self.assertTrue(verify_files(root, ["x.jsx", "x.py"], run_tests=False).passed)

    def test_behavioral_failure_is_not_syntax_success(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "test_wrong.py").write_text("def test_wrong():\n    assert 1 == 2\n")
            result = verify_files(root, ["test_wrong.py"])
            self.assertFalse(result.passed)
            self.assertEqual(result.level, "tests")

    def test_provider_secrets_are_not_inherited(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "secret", "AWS_SECRET_ACCESS_KEY": "secret"}):
            self.assertNotIn("GEMINI_API_KEY", execution_env())
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", execution_env())
