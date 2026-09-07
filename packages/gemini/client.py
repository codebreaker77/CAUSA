"""Causa × Gemini API Client.

Heterogeneous multi-model routing using Google Gemini API.
Endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

Model Tier Architecture (all confirmed working as of 2026-09-07):
  ORCHESTRATOR → gemini-3.8-flash   (reasoning model, plans & decomposes tasks)
  WORKER       → gemini-3.5-flash   (reasoning model, writes feature code)
  FAST         → gemini-3.5-flash-lite  (fast, cheap, CRUD/components/tests)
  NANO         → gemini-3.1-flash-lite  (fastest, cheapest, stubs/docs)

All tiers are heterogeneous — different model per task type.
Orchestration is done by ORCHESTRATOR only. Workers never orchestrate.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Iterator, Tuple
from pydantic import BaseModel


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


# ---------------------------------------------------------------------------
# Model Tier Registry
# ---------------------------------------------------------------------------

class GeminiTier:
    ORCHESTRATOR = "orchestrator"  # Plans, decomposes, routes — the GOOD model
    WORKER       = "worker"        # Complex feature code, architecture
    FAST         = "fast"          # Standard features, CRUD, components
    NANO         = "nano"          # Tests, docs, stubs — cheapest


# Confirmed working models on this API key (probed 2026-09-07)
TIER_MODELS: Dict[str, List[str]] = {
    GeminiTier.ORCHESTRATOR: [
        "gemini-3.8-flash",       # Reasoning model — deep thinking for task decomposition
        "gemini-3.5-flash",       # Fallback reasoning model
        "gemini-3.5-flash-lite",  # Emergency fallback
    ],
    GeminiTier.WORKER: [
        "gemini-3.5-flash",       # Reasoning model — best for complex code
        "gemini-3.8-flash",       # Alt: heavier reasoning
        "gemini-3.5-flash-lite",  # Fallback
    ],
    GeminiTier.FAST: [
        "gemini-3.5-flash-lite",  # Fast, cheap, good enough for standard features
        "gemini-3.1-flash-lite",  # Fallback: even faster
    ],
    GeminiTier.NANO: [
        "gemini-3.1-flash-lite",  # Fastest, cheapest — unit tests, docs
        "gemini-3.5-flash-lite",  # Fallback
    ],
}

# Approximate costs per million tokens
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.8-flash":      {"input": 0.10, "output": 0.40, "thinking": 0.035},
    "gemini-3.5-flash":      {"input": 0.10, "output": 0.40, "thinking": 0.035},
    "gemini-3.5-flash-lite": {"input": 0.02, "output": 0.08, "thinking": 0.0},
    "gemini-3.1-flash-lite": {"input": 0.01, "output": 0.04, "thinking": 0.0},
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class GeminiGenerationResult(BaseModel):
    success: bool
    model: str
    tier: str = ""
    response_text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    error_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Core Client
# ---------------------------------------------------------------------------

class GeminiClient:
    """Unified Gemini API client for heterogeneous multi-model routing."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Add it to .env: GEMINI_API_KEY=AQ..."
            )

    def _url(self, model: str) -> str:
        return f"{GEMINI_BASE_URL}/{model}:generateContent?key={self.api_key}"

    # ------------------------------------------------------------------
    # 1. Core Generate
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str = "gemini-3.5-flash-lite",
        tier: str = GeminiTier.FAST,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> GeminiGenerationResult:
        """Send a generateContent request to the Gemini API."""
        contents = []
        if system_prompt:
            # Gemini uses system_instruction at top level
            pass  # handled in payload below
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: Dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url(model),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                duration_ms = (time.monotonic() - t0) * 1000

                # Extract text
                candidate = body["candidates"][0]
                parts = candidate.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)

                # Token accounting
                usage = body.get("usageMetadata", {})
                p_tok = usage.get("promptTokenCount", 0)
                c_tok = usage.get("candidatesTokenCount", 0)
                t_tok = usage.get("thoughtsTokenCount", 0)
                total = usage.get("totalTokenCount", p_tok + c_tok)
                cost = self._estimate_cost(model, p_tok, c_tok, t_tok)

                return GeminiGenerationResult(
                    success=True,
                    model=model,
                    tier=tier,
                    response_text=text,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    thinking_tokens=t_tok,
                    total_tokens=total,
                    cost_usd=cost,
                    duration_ms=duration_ms,
                )

        except urllib.error.HTTPError as e:
            duration_ms = (time.monotonic() - t0) * 1000
            try:
                body = json.loads(e.read().decode("utf-8"))
                err = body.get("error", {})
                err_type = "QuotaError" if e.code == 429 else "APIError"
                err_msg = err.get("message", str(e))
            except Exception:
                err_type = "HTTPError"
                err_msg = f"HTTP {e.code}: {e.reason}"
            return GeminiGenerationResult(
                success=False, model=model, tier=tier,
                error=err_msg, error_type=err_type, duration_ms=duration_ms,
            )
        except Exception as ex:
            return GeminiGenerationResult(
                success=False, model=model, tier=tier,
                error=str(ex), error_type="NetworkError",
            )

    # ------------------------------------------------------------------
    # 2. Tier-Aware Routing with Fallback
    # ------------------------------------------------------------------

    def generate_for_tier(
        self,
        tier: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> GeminiGenerationResult:
        """Generate using the best model for a tier, with automatic fallback."""
        models = TIER_MODELS.get(tier, TIER_MODELS[GeminiTier.FAST])
        last_result = None
        for model in models:
            result = self.generate(
                prompt=prompt, model=model, tier=tier,
                system_prompt=system_prompt, max_tokens=max_tokens,
                temperature=temperature,
            )
            if result.success:
                return result
            last_result = result
            # On quota errors, don't try more models
            if result.error_type == "QuotaError":
                return result
        return last_result

    # ------------------------------------------------------------------
    # 3. Orchestrator: Task Decomposition
    # ------------------------------------------------------------------

    ORCHESTRATOR_SYSTEM = """You are Astra, the Causa swarm orchestrator.
Given a user goal, decompose it into concrete subtasks for a coding agent swarm.

Rules:
- Each subtask MUST have: title, description, tier (orchestrator/worker/fast/nano), target_file
- tier assignment:
  * orchestrator: architecture decisions, system design
  * worker: complex logic, algorithms, core business code  
  * fast: standard features, API routes, database models, React components
  * nano: unit tests, documentation, type stubs, formatting
- Return ONLY valid JSON. No markdown, no explanation.
- Format: {"subtasks": [{"title": "...", "description": "...", "tier": "...", "target_file": "...", "dependencies": []}]}"""

    def decompose_goal(self, goal: str) -> Dict:
        """Use the ORCHESTRATOR model to decompose a user goal into subtasks."""
        result = self.generate_for_tier(
            tier=GeminiTier.ORCHESTRATOR,
            prompt=f"Goal: {goal}\n\nDecompose into 3-6 subtasks as JSON.",
            system_prompt=self.ORCHESTRATOR_SYSTEM,
            max_tokens=4096,
            temperature=0.1,
        )
        if not result.success:
            return {"subtasks": [], "error": result.error}
        # Extract JSON from response
        text = result.response_text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        try:
            plan = json.loads(text)
            plan["orchestrator_model"] = result.model
            plan["orchestrator_tokens"] = result.total_tokens
            plan["orchestrator_cost_usd"] = result.cost_usd
            return plan
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    plan = json.loads(match.group(0))
                    plan["orchestrator_model"] = result.model
                    return plan
                except Exception:
                    pass
            return {"subtasks": [], "error": "Failed to parse orchestrator JSON", "raw": text[:500]}

    # ------------------------------------------------------------------
    # 4. Worker: Code Generation
    # ------------------------------------------------------------------

    CODE_GEN_SYSTEM = """You are an expert software engineer.
Write complete, production-quality code. 
OUTPUT ONLY the file contents. No markdown fences. No explanations. No comments about what you did.
Start from line 1 of the file. Write complete, runnable code with all imports."""

    def generate_code(
        self,
        task_description: str,
        file_path: str,
        tier: str = GeminiTier.FAST,
        context: str = "",
    ) -> GeminiGenerationResult:
        """Generate complete code for a file using the appropriate model tier."""
        ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "py"
        lang_map = {"py": "Python", "ts": "TypeScript", "tsx": "TypeScript React",
                    "js": "JavaScript", "jsx": "JavaScript React", "html": "HTML"}
        lang = lang_map.get(ext, ext.upper())

        prompt_parts = [f"Language: {lang}", f"File: {file_path}"]
        if context:
            prompt_parts.append(f"\nExisting context:\n{context}")
        prompt_parts.append(f"\nTask: {task_description}")
        prompt_parts.append("\nWrite the complete file contents now:")
        prompt = "\n".join(prompt_parts)

        return self.generate_for_tier(
            tier=tier,
            prompt=prompt,
            system_prompt=self.CODE_GEN_SYSTEM,
            max_tokens=8192,
            temperature=0.15,
        )

    # ------------------------------------------------------------------
    # 5. Cost Estimation
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int, thinking_tokens: int = 0) -> float:
        pricing = MODEL_PRICING.get(model, {"input": 0.10, "output": 0.40, "thinking": 0.035})
        return (
            (prompt_tokens / 1_000_000) * pricing["input"]
            + (completion_tokens / 1_000_000) * pricing["output"]
            + (thinking_tokens / 1_000_000) * pricing.get("thinking", 0.0)
        )

    # ------------------------------------------------------------------
    # 6. Health Probe
    # ------------------------------------------------------------------

    def probe(self) -> Dict[str, Tuple[bool, str]]:
        """Probes all tier models. Returns {tier: (ok, message)}."""
        results = {}
        for tier, models in TIER_MODELS.items():
            model = models[0]
            res = self.generate("Reply: OK", model=model, tier=tier, max_tokens=50)
            if res.success:
                results[tier] = (True, f"{model} OK")
            else:
                results[tier] = (False, f"{model}: {res.error_type} — {res.error}")
        return results
