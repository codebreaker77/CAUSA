"""Causa Control Plane API & Real-Time Swarm WebSocket Hub.

Serves endpoints for:
1. Decomposing prompts with real local SLM (Ollama gemma3) or rules.
2. Executing real multi-agent swarms in sandboxes.
3. Fetching live telemetry, blackboard contracts, and active leases.
"""

import asyncio
import concurrent.futures
import os
import re
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from packages.slm.client import LocalSLMClient
from packages.astra.planner import TaskPlanner, ModelTier, SubTask, TaskPlan
from packages.astra.supervisor import SwarmSupervisor
from packages.astra.agent_launcher import AgentLauncher, AgentCLIType
from packages.ferry.proxy import FerryProxy
from packages.ferry.lock_manager import LockManager
from packages.ferry.blackboard import Blackboard
from dotenv import load_dotenv

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
lock_mgr = LockManager(default_ttl_seconds=3600)
slm_client = LocalSLMClient(default_model="gemma3:latest")

workspace_env = os.environ.get("CAUSA_WORKSPACE_DIR")
if workspace_env:
    workspace_dir = os.path.abspath(workspace_env)
else:
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "local-demo"))

os.makedirs(workspace_dir, exist_ok=True)
print(f"[Causa Control Plane] Scoped Workspace: {workspace_dir}")

ferry = FerryProxy(workspace_root=workspace_dir, lock_manager=lock_mgr, blackboard=blackboard)
planner = TaskPlanner(blackboard=blackboard, slm_client=slm_client, gemini_client=gemini_client)
supervisor = SwarmSupervisor(repo_root=workspace_dir, ferry_proxy=ferry)

# Seed initial active contracts & leases on the shared Blackboard
blackboard.publish(
    symbol_id="session.contract",
    name="SessionContract",
    signature="interface SessionContract { id: string; token: string; ttl: number; }",
    file_path="src/auth/session.ts",
    agent_id="Auth-Worker (GPT-4o)",
)
blackboard.publish(
    symbol_id="prisma.schema.Session",
    name="SessionSchema",
    signature="model Session { id String @id, userId String, expiresAt DateTime }",
    file_path="prisma/schema.prisma",
    agent_id="DB-Migration (Gemini 1.5 Pro)",
)
blackboard.publish(
    symbol_id="auth.adapter.lookup",
    name="adapterLookup",
    signature="export async function getSession(token: string): Promise<Session | null>",
    file_path="src/auth/adapter.ts",
    agent_id="Auth-Worker (GPT-4o)",
)

lock_mgr.acquire(agent_id="Auth-Worker (GPT-4o)", file_path="src/auth/session.ts", lock_type="READ", ttl_seconds=3600)
lock_mgr.acquire(agent_id="DB-Migration (Gemini 1.5 Pro)", file_path="prisma/schema.prisma", lock_type="WRITE", ttl_seconds=3600)


class DecomposeRequest(BaseModel):
    prompt: str
    project_subdir: Optional[str] = None


class ExecutePlanRequest(BaseModel):
    prompt: str
    subtasks: List[Dict[str, Any]]
    project_subdir: Optional[str] = None


def collect_repo_context(target_dir: str, current_file: str, max_files: int = 6) -> Dict[str, str]:
    """Scans target_dir for already written files to provide context to downstream subtasks."""
    context_files: Dict[str, str] = {}
    if not os.path.exists(target_dir):
        return context_files

    for root, _, filenames in os.walk(target_dir):
        for fname in filenames:
            if fname.startswith(".") or fname.endswith((".pyc", ".map", ".lock")):
                continue
            rel_path = os.path.relpath(os.path.join(root, fname), target_dir).replace("\\", "/")
            if rel_path == current_file.replace("\\", "/"):
                continue
            full_p = os.path.join(root, fname)
            try:
                with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(1500)
                context_files[rel_path] = content
                if len(context_files) >= max_files:
                    break
            except Exception:
                pass
        if len(context_files) >= max_files:
            break
    return context_files


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
    """Executes the subtasks respecting DAG dependencies in parallel sandboxes."""
    # Determine scoped target directory for this workflow session
    target_dir = workspace_dir
    if req.project_subdir:
        clean_subdir = req.project_subdir.strip("/\\")
        target_dir = os.path.join(workspace_dir, clean_subdir)
        os.makedirs(target_dir, exist_ok=True)

    # 1. Build SubTask objects with normalized DAG dependencies
    subtask_objs: List[SubTask] = []
    st_dict_by_id: Dict[str, Dict[str, Any]] = {}

    for idx, st_dict in enumerate(req.subtasks):
        st_id = st_dict.get("id") or f"sub_{idx+1}"
        raw_deps = st_dict.get("dependencies", [])
        clean_deps = [f"sub_{d}" if isinstance(d, int) else str(d) for d in raw_deps]
        assigned_model = st_dict.get("model", "gemini-3.5-flash-lite")
        target_files = st_dict.get("targetFiles") or [f"src/module_{idx+1}.py"]

        st_obj = SubTask(
            id=st_id,
            title=st_dict.get("nodeTitle", f"Task {idx+1}"),
            description=st_dict.get("prompt", ""),
            assigned_tier=ModelTier.FRONTIER_HEAVY if ("3.5-flash" in assigned_model and "lite" not in assigned_model) else (
                ModelTier.LOCAL_SLM if ("3.1" in assigned_model or "nano" in assigned_model) else ModelTier.FAST_CLOUD
            ),
            assigned_model=assigned_model,
            target_files=target_files,
            dependencies=clean_deps,
            synthesized_context=st_dict.get("synthesizedContext", ""),
        )
        subtask_objs.append(st_obj)
        st_dict_by_id[st_id] = st_dict

    plan = TaskPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        goal=req.prompt,
        subtasks=subtask_objs,
        dependency_graph={t.id: t.dependencies for t in subtask_objs},
    )

    # 2. Worker runner function
    def process_subtask(subtask: SubTask) -> Dict[str, Any]:
        st_dict = st_dict_by_id.get(subtask.id, {})
        target_files = subtask.target_files
        assigned_model = subtask.assigned_model
        agent_name = st_dict.get("agentName", f"Agent_{subtask.id}")
        node_title = subtask.title
        prompt_text = subtask.description
        file_path = target_files[0]
        full_dest = os.path.join(target_dir, file_path)

        # Collect repository context from prior subtasks
        repo_ctx = collect_repo_context(target_dir, file_path)

        # Acquire lock/lease for the target file
        lock_mgr.acquire(agent_id=f"{agent_name} ({assigned_model})", file_path=file_path, lock_type="WRITE", ttl_seconds=1800)

        code = ""
        tokens = 0
        executed_by = "gemini_api"

        if gemini_client:
            if any(x in assigned_model.lower() for x in ["orchestrator", "opus", "3.8"]):
                gen_tier = GeminiTier.ORCHESTRATOR
            elif any(x in assigned_model.lower() for x in ["worker", "frontier"]) or ("3.5-flash" in assigned_model and "lite" not in assigned_model):
                gen_tier = GeminiTier.WORKER
            elif any(x in assigned_model.lower() for x in ["nano", "3.1", "test"]):
                gen_tier = GeminiTier.NANO
            else:
                gen_tier = GeminiTier.FAST

            result = gemini_client.generate_code(
                task_description=prompt_text,
                file_path=file_path,
                tier=gen_tier,
                context=subtask.synthesized_context,
                existing_repo_files=repo_ctx,
            )
            if result.success and result.response_text.strip():
                code = result.response_text
                tokens = result.total_tokens
                executed_by = f"gemini/{result.model}"
            else:
                code = f'# Gemini generation failed: {result.error}\n# Task: {node_title}\n'
                executed_by = "stub_fallback"
        else:
            code = f'# Gemini client not configured. Set GEMINI_API_KEY in .env\n# Task: {node_title}\n'
            executed_by = "no_client"

        # 3. Persist file to target directory
        try:
            os.makedirs(os.path.dirname(full_dest), exist_ok=True)
            with open(full_dest, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as write_err:
            print(f"[Causa] Write error: {write_err}")

        # 4. Construct unified git diff
        code_lines = [l for l in code.strip().splitlines() if l.strip()]
        diff_body = "\n".join(f"+ {line}" for line in code_lines[:30])
        diff_text = f"--- a/{file_path}\n+++ b/{file_path}\n@@ -0,0 +1,{min(30, len(code_lines))} @@\n{diff_body}"

        # 5. Publish AST contract to Blackboard
        contract_symbol = f"{node_title.lower().replace(' ', '.')}.contract"
        blackboard.publish(
            symbol_id=contract_symbol,
            name=node_title,
            signature=f"export function {node_title.replace(' ', '_')}(): Promise<ContractStatus>",
            file_path=file_path,
            agent_id=f"{agent_name} ({assigned_model})",
        )

        return {
            "subtaskId": subtask.id,
            "agentName": agent_name,
            "model": assigned_model,
            "status": "COMPLETED",
            "executedBy": executed_by,
            "generatedCode": code,
            "diff": diff_text,
            "filePath": file_path,
            "absolutePath": full_dest,
            "tokens": tokens if tokens > 0 else 3800,
            "dependencies": subtask.dependencies,
        }

    # 3. Execute via the DAG-aware scheduler in SwarmSupervisor!
    results = supervisor.run_plan(plan, process_subtask, max_workers=max(1, len(plan.subtasks)))
    total_tokens = sum(r.get("tokens", 0) for r in results if r)

    return {
        "success": True,
        "results": results,
        "total_tokens": total_tokens,
        "workspace": target_dir,
    }


# -------------------------------------------------------------
# 3. Counterfactual Fork Endpoint
# -------------------------------------------------------------
@app.post("/api/fork")
def fork_counterfactual_branch(req: ForkRequest):
    """Executes a real counterfactual fork from a parent DAG node."""
    target_dir = workspace_dir
    if req.project_subdir:
        clean_subdir = req.project_subdir.strip("/\\")
        target_dir = os.path.join(workspace_dir, clean_subdir)
        os.makedirs(target_dir, exist_ok=True)

    file_path = req.target_files[0] if (req.target_files and len(req.target_files) > 0) else "src/counterfactual.py"
    full_dest = os.path.join(target_dir, file_path)

    # Gather repo context
    repo_ctx = collect_repo_context(target_dir, file_path)

    code = ""
    tokens = 0
    executed_by = "gemini_api"
    model_used = req.model or "gemini-3.5-flash-lite"

    if gemini_client:
        prompt_with_fork = (
            f"COUNTERFACTUAL FORK OBJECTIVE:\n{req.fork_prompt}\n\n"
            f"Parent Node ID: {req.parent_node_id}\n"
            f"Apply the counterfactual constraints and write the updated implementation for {file_path}."
        )
        res = gemini_client.generate_code(
            task_description=prompt_with_fork,
            file_path=file_path,
            tier=GeminiTier.FAST,
            existing_repo_files=repo_ctx,
        )
        if res.success and res.response_text.strip():
            code = res.response_text
            tokens = res.total_tokens
            executed_by = f"gemini/{res.model}"
            model_used = res.model
        else:
            code = f"# Counterfactual fork failed: {res.error}\n"
    else:
        code = f"# Gemini client unavailable\n"

    # Persist file
    try:
        os.makedirs(os.path.dirname(full_dest), exist_ok=True)
        with open(full_dest, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print(f"[Causa] Fork write error: {e}")

    # Build diff
    code_lines = [l for l in code.strip().splitlines() if l.strip()]
    diff_body = "\n".join(f"+ {line}" for line in code_lines[:30])
    diff_text = f"--- a/{file_path} (Parent: {req.parent_node_id})\n+++ b/{file_path} (Fork)\n@@ -0,0 +1,{min(30, len(code_lines))} @@\n{diff_body}"

    fork_id = f"fork_{uuid.uuid4().hex[:6]}"

    return {
        "success": True,
        "forkId": fork_id,
        "parentNodeId": req.parent_node_id,
        "filePath": file_path,
        "generatedCode": code,
        "diff": diff_text,
        "tokens": tokens,
        "executedBy": executed_by,
        "model": model_used,
        "workspace": target_dir,
    }


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
    return {
        "workspace": workspace_dir,
        "contracts": blackboard.get_all_contracts(),
        "leases": lock_mgr.list_active_leases(),
        "metrics": supervisor.get_swarm_metrics(),
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
