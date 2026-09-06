"""Unit tests for Astra Real CLI Agent Launcher (Codex, OpenCode, Gemini/Antigravity)."""

import os
import tempfile
import unittest
from packages.astra.agent_launcher import AgentLauncher, AgentCLIType


class TestAstraAgentLauncher(unittest.TestCase):
    def test_discover_installed_agents(self):
        discovered = AgentLauncher.discover_installed_agents()
        self.assertIsInstance(discovered, dict)
        
        # Verify discovered paths for codex and opencode on user machine
        self.assertIn("codex", discovered)
        self.assertIn("opencode", discovered)
        self.assertIn("gemini", discovered)
        print(f"\nDiscovered Agent CLIs on host: {discovered}")

    def test_build_codex_command(self):
        cmd, env = AgentLauncher.build_command(
            agent_type=AgentCLIType.CODEX,
            prompt="Refactor auth.py",
            working_dir="/test/dir",
            model="o3-mini",
        )
        self.assertIn("exec", cmd)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertIn("-m o3-mini", cmd)
        self.assertIn("Refactor auth.py", cmd)

    def test_build_opencode_command(self):
        cmd, env = AgentLauncher.build_command(
            agent_type=AgentCLIType.OPENCODE,
            prompt="Build REST API",
            working_dir="/test/dir",
            model="anthropic/claude-3-5-sonnet",
        )
        self.assertIn("run", cmd)
        self.assertIn("Build REST API", cmd)

    def test_build_gemini_antigravity_command(self):
        cmd, env = AgentLauncher.build_command(
            agent_type=AgentCLIType.GEMINI_ANTIGRAVITY,
            prompt="Audit causal DAG",
            working_dir="/test/dir",
        )
        self.assertIn("Audit causal DAG", cmd)


if __name__ == "__main__":
    unittest.main()
