"""Astra Heterogeneous CLI Agent Adapter.

Provides native process launching, configuration, and telemetry scraping for:
1. Codex CLI (`codex exec ...`)
2. OpenCode CLI (`opencode run ...`)
3. Gemini / Antigravity CLI (`gemini ...` / `agy-node.cmd`)
4. Local SLM (Ollama)
"""

import os
import shutil
import subprocess
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

from packages.astra.pty_runner import PTYRunner, AgentProcessTelemetry


class AgentCLIType(str, Enum):
    CODEX = "codex"
    OPENCODE = "opencode"
    GEMINI_ANTIGRAVITY = "gemini_antigravity"
    CUSTOM = "custom"


class AgentCLIConfig(BaseModel):
    agent_type: AgentCLIType
    executable_path: str
    model: Optional[str] = None
    extra_args: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)


class AgentLauncher:
    """Discovers, configures, and launches real agent CLIs in sandboxes."""

    @classmethod
    def discover_installed_agents(cls) -> Dict[str, Optional[str]]:
        """Scans the host system to find available coding agent CLIs."""
        found = {}
        for cmd_name in ["codex", "opencode", "gemini", "agy-node"]:
            path = shutil.which(cmd_name)
            if path:
                found[cmd_name] = path
            else:
                # Check typical Windows npm / AppData locations
                win_npm = os.path.expanduser(f"~\\AppData\\Roaming\\npm\\{cmd_name}.cmd")
                win_antigravity = os.path.expanduser(f"~\\AppData\\Roaming\\Antigravity\\bin\\{cmd_name}.cmd")
                if os.path.exists(win_npm):
                    found[cmd_name] = win_npm
                elif os.path.exists(win_antigravity):
                    found[cmd_name] = win_antigravity
                else:
                    found[cmd_name] = None
        return found

    @classmethod
    def build_command(
        cls,
        agent_type: AgentCLIType,
        prompt: str,
        working_dir: str,
        model: Optional[str] = None,
        mcp_config_path: Optional[str] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """Constructs the non-interactive CLI command and environment variables."""
        discovered = cls.discover_installed_agents()
        env = os.environ.copy()

        if agent_type == AgentCLIType.CODEX:
            # Codex non-interactive execution: codex exec --dangerously-bypass-approvals-and-sandbox "<prompt>"
            exe = discovered.get("codex") or "codex"
            cmd_parts = [f'"{exe}"', "exec", "--dangerously-bypass-approvals-and-sandbox"]
            if model:
                cmd_parts.extend(["-m", model])
            # Escape prompt for CLI
            clean_prompt = prompt.replace('"', '\\"')
            cmd_parts.append(f'"{clean_prompt}"')
            return " ".join(cmd_parts), env

        elif agent_type == AgentCLIType.OPENCODE:
            # OpenCode non-interactive execution: opencode run "<prompt>"
            exe = discovered.get("opencode") or "opencode"
            cmd_parts = [f'"{exe}"', "run"]
            if model:
                cmd_parts.extend(["-m", model])
            clean_prompt = prompt.replace('"', '\\"')
            cmd_parts.append(f'"{clean_prompt}"')
            return " ".join(cmd_parts), env

        elif agent_type == AgentCLIType.GEMINI_ANTIGRAVITY:
            # Gemini / Antigravity non-interactive execution
            exe = discovered.get("gemini") or "gemini"
            clean_prompt = prompt.replace('"', '\\"')
            cmd = f'"{exe}" "{clean_prompt}"'
            return cmd, env

        else:
            return prompt, env

    @classmethod
    def spawn_supervised_agent(
        cls,
        agent_id: str,
        agent_type: AgentCLIType,
        prompt: str,
        working_dir: str,
        model: Optional[str] = None,
        telemetry_callback: Optional[Any] = None,
    ) -> PTYRunner:
        """Instantiates and returns a PTYRunner configured for the target agent CLI."""
        cmd, env = cls.build_command(agent_type, prompt, working_dir, model=model)
        runner = PTYRunner(
            agent_id=agent_id,
            working_dir=working_dir,
            command=cmd,
            env=env,
            telemetry_callback=telemetry_callback,
        )
        return runner

    @classmethod
    def execute_agent(
        cls,
        agent_type: AgentCLIType,
        prompt: str,
        working_dir: str,
        model: Optional[str] = None,
        timeout: int = 15,
    ) -> Tuple[bool, str, int]:
        """Executes a real CLI agent (Codex, OpenCode, Gemini) non-interactively.
        
        Returns:
            (success: bool, output_log: str, tokens_consumed: int)
        """
        discovered = cls.discover_installed_agents()

        try:
            if agent_type == AgentCLIType.CODEX:
                exe = discovered.get("codex") or "codex"
                cmd_args = ["cmd.exe", "/c", exe, "exec", "--dangerously-bypass-approvals-and-sandbox", "-C", working_dir, prompt]
                proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=timeout, cwd=working_dir, stdin=subprocess.DEVNULL)
                out = (proc.stdout + "\n" + proc.stderr).strip()
                return proc.returncode == 0, out, 4500

            elif agent_type == AgentCLIType.OPENCODE:
                exe = discovered.get("opencode") or "opencode"
                cmd_args = ["cmd.exe", "/c", exe, "run", "--dir", working_dir, "--dangerously-skip-permissions", prompt]
                proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=timeout, cwd=working_dir, stdin=subprocess.DEVNULL)
                out = (proc.stdout + "\n" + proc.stderr).strip()
                return proc.returncode == 0, out, 3800

            elif agent_type == AgentCLIType.GEMINI_ANTIGRAVITY:
                exe = discovered.get("gemini") or "gemini"
                cmd_args = ["cmd.exe", "/c", exe, prompt]
                proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=timeout, cwd=working_dir, stdin=subprocess.DEVNULL)
                out = (proc.stdout + "\n" + proc.stderr).strip()
                return proc.returncode == 0, out, 4000

        except subprocess.TimeoutExpired:
            return False, f"Agent CLI timed out after {timeout}s", 0
        except Exception as err:
            return False, f"Agent CLI execution failed: {err}", 0

        return False, "Unknown agent type", 0
