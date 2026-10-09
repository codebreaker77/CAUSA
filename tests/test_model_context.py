import unittest
from unittest.mock import patch
from packages.gemini.client import GeminiClient, GeminiGenerationResult


class TestModelContext(unittest.TestCase):
    def test_complete_target_context_is_preserved(self):
        client = GeminiClient(api_key="fake")
        content = "a" * 4000 + "IMPORTANT_TAIL"
        with patch.object(client, "generate_for_tier", return_value=GeminiGenerationResult(
                success=True, model="fake", response_text="x=1")) as generate:
            client.generate_code("fix bug", "x.py", existing_repo_files={"x.py": content})
            self.assertIn(content, generate.call_args.kwargs["prompt"])
            self.assertNotIn("lucide", generate.call_args.kwargs["system_prompt"])
        self.assertNotIn("10-25", client.ORCHESTRATOR_SYSTEM)
