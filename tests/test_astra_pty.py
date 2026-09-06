"""Unit tests for Astra PTY Process Supervision & Telemetry Scraper (Phase 2)."""

import os
import sys
import tempfile
import time
import unittest
from packages.astra.pty_runner import PTYRunner


class TestAstraPTYRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_run_script_and_scrape_tokens(self):
        # Create a mock agent script that simulates an agent CLI outputting status & tokens
        script_code = """
import time
import sys

print("Initializing agent...")
print("Model: claude-3-5-sonnet")
print("Thinking about architecture...")
time.sleep(0.1)
print("Running tool: write_file")
print("Tokens: 14.5k / 200k | Cost: $0.05")
time.sleep(0.1)
print("Completed successfully!")
"""
        script_path = os.path.join(self.temp_dir, "mock_agent.py")
        with open(script_path, "w") as f:
            f.write(script_code)

        telemetry_snapshots = []
        def on_telemetry(t):
            telemetry_snapshots.append(t)

        runner = PTYRunner(
            agent_id="test-agent-1",
            working_dir=self.temp_dir,
            command=f"{sys.executable} mock_agent.py",
            telemetry_callback=on_telemetry,
        )

        started = runner.start()
        self.assertTrue(started)

        exit_code = runner.wait(timeout_seconds=5)
        self.assertEqual(exit_code, 0)

        # Verify scraped telemetry
        self.assertEqual(runner.telemetry.model_name, "claude-3-5-sonnet")
        self.assertEqual(runner.telemetry.tokens_used, 14500)
        self.assertEqual(runner.telemetry.tokens_limit, 200000)
        self.assertEqual(runner.telemetry.cost_usd, 0.05)
        self.assertEqual(runner.telemetry.state, "DONE")
        self.assertGreater(len(telemetry_snapshots), 3)

    def test_interactive_input_injection(self):
        # Script that waits for user input from stdin
        script_code = """
import sys
val = input()
print(f"ECHO: {val}")
"""
        script_path = os.path.join(self.temp_dir, "echo_agent.py")
        with open(script_path, "w") as f:
            f.write(script_code)

        runner = PTYRunner(
            agent_id="test-echo-agent",
            working_dir=self.temp_dir,
            command=f"{sys.executable} echo_agent.py",
        )
        runner.start()
        time.sleep(0.2)

        # Inject slash command / tokens
        injected = runner.send_input("/tokens\n")
        self.assertTrue(injected)

        exit_code = runner.wait(timeout_seconds=5)
        self.assertEqual(exit_code, 0)
        self.assertTrue(any("ECHO: /tokens" in log for log in runner.telemetry.recent_logs))


if __name__ == "__main__":
    unittest.main()
