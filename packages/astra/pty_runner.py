"""Astra PTY Process Supervision & Telemetry Scraper.

Runs CLI-driven and MCP-compliant agent processes (Aider, OpenCode, Claude Code, Codex)
inside controlled pseudo-terminals / piped subprocesses.

Key capabilities:
1. Universal Process Supervision: Spawns agent CLIs with their working directory
   anchored to their isolated Git worktree.
2. Passive ANSI & Token Scraper: Continuously inspects stdout/stderr in real time
   to extract:
   - Token usage (Tokens: 14.2k / 200k, prompt/completion token breakdown).
   - Incurred cost ($0.04).
   - Active model name (claude-3-5-sonnet, gpt-4o, ollama/qwen).
   - Current agent state (THINKING, EXECUTING, IDLE, COMPLETED, FAILED).
3. Active Probing: Injects commands (e.g. /tokens, /status) into stdin.
4. Process Watchdog: Enforces CPU/runtime timeouts and handles graceful termination.
"""

import os
import re
import signal
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional, Any
from pydantic import BaseModel, Field


class AgentProcessTelemetry(BaseModel):
    agent_id: str
    pid: Optional[int] = None
    state: str = "INITIALIZING"  # INITIALIZING, RUNNING, THINKING, IDLE, DONE, FAILED, TERMINATED
    model_name: Optional[str] = None
    tokens_used: int = 0
    tokens_limit: Optional[int] = None
    cost_usd: float = 0.0
    recent_logs: List[str] = Field(default_factory=list)
    exit_code: Optional[int] = None
    started_at: int = Field(default_factory=lambda: int(time.time()))
    last_updated_at: int = Field(default_factory=lambda: int(time.time()))


class PTYRunner:
    """Spawns and monitors agent CLI subprocesses with telemetry scraping."""

    # Regex patterns for scraping agent status bars and tokens across popular CLIs
    TOKEN_REGEX = re.compile(
        r"(?:Tokens?|Context):\s*([\d\.]+[kM]?)\s*/\s*([\d\.]+[kM]?)",
        re.IGNORECASE,
    )
    COST_REGEX = re.compile(r"Cost:\s*\$([\d\.]+)", re.IGNORECASE)
    MODEL_REGEX = re.compile(
        r"(?:Model|Engine):\s*([\w\.\-\:]+)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        agent_id: str,
        working_dir: str,
        command: str,
        env: Optional[Dict[str, str]] = None,
        telemetry_callback: Optional[Callable[[AgentProcessTelemetry], None]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.working_dir = working_dir
        self.command = command
        self.custom_env = env or {}
        self.telemetry_callback = telemetry_callback

        self.telemetry = AgentProcessTelemetry(agent_id=agent_id)
        self.process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._lock = threading.Lock()

    # -------------------------------------------------------------
    # 1. Start Agent Process
    # -------------------------------------------------------------
    def start(self) -> bool:
        """Launches the agent process with stdout/stderr piped for interception."""
        merged_env = os.environ.copy()
        merged_env.update(self.custom_env)
        # Ensure unbuffered I/O for real-time telemetry
        merged_env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.working_dir,
                env=merged_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # Line buffered
            )
            self._is_running = True
            self.telemetry.pid = self.process.pid
            self.telemetry.state = "RUNNING"
            self._notify_telemetry()

            # Start background reader thread
            self._reader_thread = threading.Thread(
                target=self._stream_reader_loop,
                daemon=True,
            )
            self._reader_thread.start()
            return True
        except Exception as err:
            self.telemetry.state = "FAILED"
            self.telemetry.recent_logs.append(f"Failed to start process: {str(err)}")
            self._notify_telemetry()
            return False

    # -------------------------------------------------------------
    # 2. Real-Time Stream Reader & Scraper
    # -------------------------------------------------------------
    def _stream_reader_loop(self) -> None:
        """Continuously reads stdout and parses tokens, cost, and state."""
        if not self.process or not self.process.stdout:
            return

        for line in iter(self.process.stdout.readline, ""):
            line_str = line.strip()
            if not line_str:
                continue

            with self._lock:
                self._scrape_telemetry_line(line_str)
                self.telemetry.recent_logs.append(line_str)
                # Keep log buffer bounded to latest 100 lines
                if len(self.telemetry.recent_logs) > 100:
                    self.telemetry.recent_logs.pop(0)
                self.telemetry.last_updated_at = int(time.time())

            self._notify_telemetry()

        # Process exited
        self.process.poll()
        with self._lock:
            self._is_running = False
            self.telemetry.exit_code = self.process.returncode
            self.telemetry.state = "DONE" if self.process.returncode == 0 else "FAILED"
            self.telemetry.last_updated_at = int(time.time())

        self._notify_telemetry()

    def _scrape_telemetry_line(self, line: str) -> None:
        """Inspects an output line for token, cost, and model signatures."""
        # 1. Scrape Tokens (e.g. Tokens: 12.5k / 200k)
        token_match = self.TOKEN_REGEX.search(line)
        if token_match:
            used_str, limit_str = token_match.group(1), token_match.group(2)
            self.telemetry.tokens_used = self._parse_k_number(used_str)
            self.telemetry.tokens_limit = self._parse_k_number(limit_str)

        # 2. Scrape Cost (e.g. Cost: $0.04)
        cost_match = self.COST_REGEX.search(line)
        if cost_match:
            try:
                self.telemetry.cost_usd = float(cost_match.group(1))
            except ValueError:
                pass

        # 3. Scrape Model
        model_match = self.MODEL_REGEX.search(line)
        if model_match:
            self.telemetry.model_name = model_match.group(1)

        # 4. Scrape State heuristics
        lower_line = line.lower()
        if "thinking" in lower_line or "reasoning" in lower_line:
            self.telemetry.state = "THINKING"
        elif "tool:" in lower_line or "running tool" in lower_line or "calling" in lower_line:
            self.telemetry.state = "RUNNING"
        elif "completed" in lower_line or "success" in lower_line:
            self.telemetry.state = "DONE"

    # -------------------------------------------------------------
    # 3. Interactive Input Injection
    # -------------------------------------------------------------
    def send_input(self, text: str) -> bool:
        """Injects text or slash commands (e.g. /tokens, /status) into process stdin."""
        if not self._is_running or not self.process or not self.process.stdin:
            return False

        try:
            if not text.endswith("\n"):
                text += "\n"
            self.process.stdin.write(text)
            self.process.stdin.flush()
            return True
        except Exception:
            return False

    # -------------------------------------------------------------
    # 4. Termination & Teardown
    # -------------------------------------------------------------
    def stop(self, timeout_seconds: int = 5) -> None:
        """Gracefully terminates the agent process with fallback to kill."""
        if not self.process or not self._is_running:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self.process.kill()
        except Exception:
            pass
        finally:
            self._is_running = False
            self.telemetry.state = "TERMINATED"
            self._notify_telemetry()

    def wait(self, timeout_seconds: Optional[int] = None) -> int:
        """Blocks until the agent process completes or timeout expires."""
        if not self.process:
            return -1
        try:
            code = self.process.wait(timeout=timeout_seconds)
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=2.0)

            with self._lock:
                self._is_running = False
                self.telemetry.exit_code = code
                self.telemetry.state = "DONE" if code == 0 else "FAILED"
                self.telemetry.last_updated_at = int(time.time())
            self._notify_telemetry()
            return code
        except subprocess.TimeoutExpired:
            self.stop()
            return -1

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------
    def _notify_telemetry(self) -> None:
        if self.telemetry_callback:
            try:
                self.telemetry_callback(self.telemetry.model_copy())
            except Exception:
                pass

    @staticmethod
    def _parse_k_number(value_str: str) -> int:
        """Converts strings like '14.2k' or '1.2M' or '500' to integer."""
        v = value_str.strip().lower()
        try:
            if v.endswith("k"):
                return int(float(v[:-1]) * 1000)
            elif v.endswith("m"):
                return int(float(v[:-1]) * 1000000)
            return int(float(v))
        except Exception:
            return 0
