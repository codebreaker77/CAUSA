"""Causa Control Plane API & Real-Time Swarm WebSocket Hub.

Serves endpoints for:
1. Decomposing prompts with real local SLM (Ollama gemma3) or rules.
2. Executing real multi-agent swarms in sandboxes.
3. Fetching live telemetry, blackboard contracts, and active leases.
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from packages.slm.client import LocalSLMClient
from packages.astra.planner import TaskPlanner, ModelTier, SubTask, TaskPlan
from packages.ferry.blackboard import Blackboard
from dotenv import load_dotenv
from pathlib import Path
from packages.paths import workspace_path
from packages.astra.runtime import ExecutionRuntime

load_dotenv()  # Loads .env file

try:
    from packages.gemini.client import GeminiClient, GeminiTier
    gemini_client = GeminiClient()
    print(f"[Causa] Gemini API ready")
except Exception as e:
    gemini_client = None
    print(f"[Causa] Gemini API unavailable: {e}")

app = FastAPI(title="Causa Control Plane API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State & Scoped Workspace Resolution
blackboard = Blackboard()
slm_client = LocalSLMClient(default_model="gemma3:latest")

workspace_env = os.environ.get("CAUSA_WORKSPACE_DIR")
if workspace_env:
    workspace_dir = os.path.abspath(workspace_env)
else:
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "local-demo"))

os.makedirs(workspace_dir, exist_ok=True)
print(f"[Causa Control Plane] Scoped Workspace: {workspace_dir}")

planner = TaskPlanner(blackboard=blackboard, slm_client=slm_client, gemini_client=gemini_client)

runtime = ExecutionRuntime(Path(workspace_dir) / ".causa")
app.state.runtime = runtime
from apps.api.routers.dag import router as runs_router
app.include_router(runs_router)


class DecomposeRequest(BaseModel):
    prompt: str
    project_subdir: Optional[str] = None


class ExecutePlanRequest(BaseModel):
    prompt: str
    subtasks: List[Dict[str, Any]]
    project_subdir: Optional[str] = None


class ForkRequest(BaseModel):
    parent_node_id: str
    fork_prompt: str
    target_files: Optional[List[str]] = None
    project_subdir: Optional[str] = None
    model: Optional[str] = None


# -------------------------------------------------------------
# 1. Real SLM / Gemini Decomposition Endpoint
# -------------------------------------------------------------
@app.post("/api/decompose")
def decompose_prompt(req: DecomposeRequest):
    """Uses Gemini API or real local SLM to decompose prompt and assign model tiers."""
    prompt_text = req.prompt.strip()

    # Check if local SLM is available
    is_slm_live = slm_client.is_available()

    # If Gemini available, use it for real AI-powered decomposition
    zen_plan = None
    if gemini_client:
        zen_plan = gemini_client.decompose_goal(prompt_text)

    # Generate plan via Astra planner (for fallback & tier routing)
    plan = planner.create_plan(prompt_text)

    # Format proposed subtasks for dashboard UI with real heterogeneous Gemini agents
    proposed = []
    agent_mapping = {
        ModelTier.FRONTIER_HEAVY: ("a1", "Gemini-Architect"),
        ModelTier.FAST_CLOUD:     ("a2", "Gemini-Worker"),
        ModelTier.LOCAL_SLM:      ("a3", "Gemini-Nano"),
    }

    # If Gemini returned subtasks, merge them into the plan format
    if zen_plan and zen_plan.get("subtasks"):
        for idx, st in enumerate(zen_plan["subtasks"]):
            sub_id = st.get("id") or f"sub_{idx + 1}"
            raw_deps = st.get("dependencies", [])
            clean_deps = []
            for d in raw_deps:
                if isinstance(d, int):
                    clean_deps.append(f"sub_{d}")
                elif str(d).isdigit():
                    clean_deps.append(f"sub_{d}")
                else:
                    clean_deps.append(str(d))

            tier_str = st.get("tier", "fast").lower()
            if tier_str in ("orchestrator", "worker", "reasoner"):
                tier_key = ModelTier.FRONTIER_HEAVY
                model_name = "gemini-3.5-flash"
            elif tier_str == "nano":
                tier_key = ModelTier.LOCAL_SLM
                model_name = "gemini-3.1-flash-lite"
            else:
                tier_key = ModelTier.FAST_CLOUD
                model_name = "gemini-3.5-flash-lite"

            agent_id, agent_name = agent_mapping[tier_key]
            proposed.append({
                "id": sub_id,
                "agentId": agent_id,
                "agentName": agent_name,
                "model": model_name,
                "role": f"{tier_str.upper()} Execution",
                "prompt": st.get("description", ""),
                "nodeTitle": st.get("title", f"Task {idx+1}"),
                "targetFiles": [st.get("target_file", f"src/module_{idx+1}.py")],
                "dependencies": clean_deps,
                "synthesizedContext": "",
            })
    else:
        for idx, st in enumerate(plan.subtasks):
            agent_id, agent_name = agent_mapping.get(st.assigned_tier, ("a1", "Gemini-Architect"))
            proposed.append({
                "id": st.id,
                "agentId": agent_id,
                "agentName": agent_name,
                "model": st.assigned_model,
                "role": f"{st.assigned_tier.value.upper()} Execution",
                "prompt": st.description,
                "nodeTitle": st.title,
                "targetFiles": st.target_files,
                "dependencies": st.dependencies,
                "synthesizedContext": st.synthesized_context,
            })

    return {
        "success": True,
        "goal": prompt_text,
        "is_slm_live": is_slm_live,
        "gemini_live": gemini_client is not None,
        "slm_model": slm_client.default_model if is_slm_live else "heuristic_fallback",
        "routed_by": "gemini_orchestrator" if (gemini_client and zen_plan and zen_plan.get("subtasks")) else plan.routed_by,
        "routing_tokens": zen_plan.get("orchestrator_tokens", 0) if zen_plan else plan.routing_tokens,
        "proposedSubtasks": proposed,
    }


# -------------------------------------------------------------
# 2. Execute Swarm Endpoint (DAG-Aware Parallel Scheduler)
# -------------------------------------------------------------
@app.post("/api/execute")
def execute_swarm(req: ExecutePlanRequest):
    """Execute isolated tasks and publish only a fully verified run."""
    try:
        target = workspace_path(workspace_dir, req.project_subdir) if req.project_subdir else Path(workspace_dir)
        subtasks = []
        for index, item in enumerate(req.subtasks):
            model = item.get("model", "gemini-3.5-flash-lite")
            tier = ModelTier.FRONTIER_HEAVY if "lite" not in model else (
                ModelTier.LOCAL_SLM if "3.1" in model else ModelTier.FAST_CLOUD)
            subtasks.append(SubTask(
                id=item.get("id") or f"sub_{index + 1}",
                title=item.get("nodeTitle", f"Task {index + 1}"),
                description=item.get("prompt", ""), assigned_model=model, assigned_tier=tier,
                target_files=item.get("targetFiles") or [],
                dependencies=item.get("dependencies", []),
                synthesized_context=item.get("synthesizedContext", "")))
        plan = TaskPlan(plan_id="plan_" + uuid.uuid4().hex, goal=req.prompt, subtasks=subtasks)
        return runtime.execute(plan, target, gemini_client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# -------------------------------------------------------------
# 3. Counterfactual Fork Endpoint
# -------------------------------------------------------------
@app.post("/api/fork")
def fork_counterfactual_branch(req: ForkRequest):
    """Preview an alternative from an actual recorded commit without overwriting source."""
    parent = runtime.storage.get_node(req.parent_node_id)
    if not parent or not parent.git_commit_hash:
        raise HTTPException(status_code=404, detail="Parent has no recorded checkpoint")
    try:
        parent_repo = workspace_path(runtime.state_root, f"runs/{parent.session_id}/repo")
        snapshot_id = "fork_base_" + uuid.uuid4().hex
        checkpoint = runtime.git(parent_repo, "rev-parse", "--verify", parent.git_commit_hash + "^{commit}")
        snapshot = workspace_path(runtime.state_root, snapshot_id)
        runtime.git(parent_repo, "worktree", "add", "--detach", str(snapshot), checkpoint)
        metadata = json.loads(parent.metadata or "{}")
        targets = req.target_files or [metadata.get("result", {}).get("filePath", "src/counterfactual.py")]
        task = SubTask(id="counterfactual", title="Counterfactual", description=req.fork_prompt,
                       assigned_tier=ModelTier.FAST_CLOUD,
                       assigned_model=req.model or "gemini-3.5-flash-lite", target_files=targets)
        result = runtime.execute(TaskPlan(plan_id=snapshot_id, goal=req.fork_prompt, subtasks=[task]),
                                 snapshot, gemini_client, apply=False, parent_node=parent.id)
        first = result["results"][0] if result["results"] else {}
        return {**result, "forkId": result["runId"], "parentNodeId": parent.id,
                "filePath": first.get("filePath"), "generatedCode": first.get("generatedCode", ""),
                "tokens": result["total_tokens"], "model": first.get("model"),
                "executedBy": "isolated_runtime"}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# -------------------------------------------------------------
# 3. Workspace Inspection Endpoint
# -------------------------------------------------------------
@app.get("/api/workspace")
async def get_workspace():
    return {
        "workspace_dir": workspace_dir,
        "exists": os.path.exists(workspace_dir),
        "is_git_repo": os.path.exists(os.path.join(workspace_dir, ".git")),
        "files": [f for f in os.listdir(workspace_dir) if not f.startswith(".")] if os.path.exists(workspace_dir) else [],
    }


# -------------------------------------------------------------
# 4. Telemetry & Blackboard Feed
# -------------------------------------------------------------
@app.get("/api/telemetry")
async def get_telemetry():
    runs = runtime.list_runs(1)
    latest = runs[0] if runs else {}
    return {
        "workspace": workspace_dir,
        "contracts": latest.get("contracts", []),
        "leases": [],
        "metrics": {
            "run_id": latest.get("runId"),
            "total_tokens": latest.get("total_tokens", 0),
            "total_cost_usd": latest.get("total_cost_usd", 0),
            "states": {state: sum(r["status"] == state for r in latest.get("results", []))
                       for state in ("COMPLETED", "FAILED", "BLOCKED")},
        },
    }



# -------------------------------------------------------------
# 5. Providers Status Endpoint
# -------------------------------------------------------------
@app.get("/api/providers")
def get_providers():
    """Returns status of configured model providers."""
    gemini_status = {"configured": gemini_client is not None}
    if gemini_client:
        probes = gemini_client.probe()
        gemini_status["tiers"] = {k: {"ok": v[0], "message": v[1]} for k, v in probes.items()}
    return {"gemini": gemini_status}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="127.0.0.1", port=8000, reload=True)
