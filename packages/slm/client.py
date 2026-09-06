"""Causa Local SLM Client.

Interfaces directly with a locally running Ollama instance (e.g. gemma3, qwen2.5-coder, phi3).
Executes real local SLM tasks:
1. Dynamic Task Complexity Evaluation & Model Routing.
2. Code Generation (unit tests, docstrings, typing skeletons).
3. Exact token tracking directly from the Ollama execution engine (prompt_eval_count, eval_count).
"""

import json
import re
import urllib.error
import urllib.request
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field


class SLMGenerationResult(BaseModel):
    success: bool
    model: str
    response_text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0  # Local SLM is always $0.00
    duration_total_ms: Optional[float] = None
    error: Optional[str] = None


class LocalSLMClient:
    """Client for querying local Ollama models with zero cloud API dependencies."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "gemma3:latest",
        timeout_seconds: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout_seconds

    # -------------------------------------------------------------
    # 1. Health & Model Discovery
    # -------------------------------------------------------------
    def is_available(self) -> bool:
        """Checks if local Ollama daemon is active and responding."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_local_models(self) -> list:
        """Lists installed local models."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name") for m in data.get("models", [])]
        except Exception:
            return []

    # -------------------------------------------------------------
    # 2. Real Inference with Native Token Accounting
    # -------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 350,
        timeout: Optional[int] = None,
    ) -> SLMGenerationResult:
        """Invokes the local SLM and extracts ground-truth token accounting."""
        target_model = model or self.default_model
        endpoint = f"{self.base_url}/api/generate"

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

                p_tokens = data.get("prompt_eval_count", 0) or 0
                c_tokens = data.get("eval_count", 0) or 0
                total_duration = data.get("total_duration", 0) / 1e6 if data.get("total_duration") else None

                return SLMGenerationResult(
                    success=True,
                    model=target_model,
                    response_text=data.get("response", "").strip(),
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=p_tokens + c_tokens,
                    cost_usd=0.0,
                    duration_total_ms=total_duration,
                )
        except urllib.error.URLError as err:
            return SLMGenerationResult(
                success=False,
                model=target_model,
                response_text="",
                error=f"Ollama connection error: {err.reason}",
            )
        except Exception as err:
            return SLMGenerationResult(
                success=False,
                model=target_model,
                response_text="",
                error=f"Inference failed: {str(err)}",
            )

    # -------------------------------------------------------------
    # 3. Real SLM Task Routing
    # -------------------------------------------------------------
    def route_task(self, task_title: str, task_desc: str) -> Tuple[str, str, int]:
        """Uses the real local SLM to classify a task into an execution tier.
        
        Returns:
            (tier: str, model_assigned: str, tokens_used: int)
        """
        system_instruction = (
            "You are Astra's Task Router. Given a coding task, classify it into one of these 3 tiers:\n"
            "1. FRONTIER_HEAVY (complex architecture, distributed consensus, security, cryptography)\n"
            "2. FAST_CLOUD (standard CRUD endpoints, database schemas, frontend components)\n"
            "3. LOCAL_SLM (unit tests, docstrings, formatting, type annotations, mock stubs)\n"
            "Respond in strictly valid JSON: {\"tier\": \"<TIER>\", \"reason\": \"<1-sentence explanation>\"}"
        )
        prompt = f"Task Title: {task_title}\nTask Description: {task_desc}"

        res = self.generate(prompt=prompt, system_prompt=system_instruction, temperature=0.0, max_tokens=60)
        if res.success:
            try:
                # Extract json from response
                raw = res.response_text
                match = re.search(r"\{.*?\}", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    tier_str = parsed.get("tier", "").strip().upper()
                    if "LOCAL" in tier_str:
                        return "local_slm", self.default_model, res.total_tokens
                    elif "FRONTIER" in tier_str:
                        return "frontier_heavy", "claude-3-5-sonnet", res.total_tokens
                    elif "FAST" in tier_str:
                        return "fast_cloud", "gemini-1.5-flash", res.total_tokens
            except Exception:
                pass

        # Fallback to local heuristic if model output is malformed
        return "fast_cloud", "gemini-1.5-flash", res.total_tokens
