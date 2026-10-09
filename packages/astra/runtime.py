"""Isolated generation, verification, integration and persistent causal evidence.

Git worktrees isolate edits, not operating-system permissions. Generated test
commands require a trusted local project or an external OS sandbox.
"""

import difflib
import hashlib
import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from packages.astra.planner import TaskPlan
from packages.astra.supervisor import SwarmSupervisor, validate_plan
from packages.astra.worktree import WorktreeManager
from packages.astra.verification import verify_files
from packages.ferry.proxy import FerryProxy, AgentCapabilityManifest
from packages.ferry.blackboard import Blackboard
from packages.ferry.ast_diff import ASTInspector
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.types import CausalNode, CausalNodeType, CausalEdge, CausalEdgeType
from packages.gemini.client import GeminiTier
from packages.paths import workspace_path, public_source_path


def digest(content):
    return hashlib.sha256(content).hexdigest()


def source_files(root):
    root = Path(root)
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if public_source_path(d))
        for filename in sorted(files):
            path = Path(current, filename)
            relative = path.relative_to(root).as_posix()
            if public_source_path(relative) and not path.is_symlink():
                yield relative, path


def collect_context(root, targets, max_chars=60000):
    """Keep complete files, prioritizing current targets, imports and tests."""
    available = dict(source_files(root))
    priority = lambda name: (name not in targets,
                             not name.endswith((".py", ".js", ".jsx", ".ts", ".tsx")), name)
    selected = {}
    used = 0
    for name in sorted(available, key=priority):
        try:
            content = available[name].read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        if used + len(content) > max_chars:
            if name in targets:
                raise ValueError(f"Target {name} exceeds context budget; refusing blind replacement")
            continue
        selected[name] = content
        used += len(content)
    return selected


class ExecutionRuntime:
    _projects_guard = threading.Lock()
    _project_locks = {}

    def __init__(self, state_root):
        self.state_root = Path(state_root).resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.storage = FullerenceStorage(str(self.state_root / "causal.db"))

    def git(self, root, *args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def record(self, run_id, agent_id, kind, status="success", parent=None,
               commit=None, worktree=None, prompt=None, metadata=None):
        node = CausalNode(id="node_" + uuid.uuid4().hex, session_id=run_id, agent_id=agent_id,
                          type=kind, status=status, parent_node_id=parent, git_commit_hash=commit,
                          worktree_path=str(worktree) if worktree else None,
                          prompt_snapshot=prompt, prompt_hash=digest(prompt.encode()) if prompt else None,
                          metadata=json.dumps(metadata or {}))
        self.storage.insert_node(node)
        if parent:
            self.storage.insert_edge(CausalEdge(id="edge_" + uuid.uuid4().hex,
                from_node_id=parent, to_node_id=node.id, type=CausalEdgeType.CAUSED_BY))
        return node.id

    def execute(self, plan: TaskPlan, source, client, max_workers=4, max_retries=2,
                apply=True, parent_node=None):
        validate_plan(plan)
        source = Path(source).resolve()
        for task in plan.subtasks:
            if not task.target_files:
                raise ValueError(f"Task {task.id} must specify target files")
            for relative in task.target_files:
                workspace_path(source, relative)
                if not public_source_path(relative):
                    raise ValueError("Targets must be public source files")
        with self._projects_guard:
            project_lock = self._project_locks.setdefault(str(source), threading.Lock())
        if not project_lock.acquire(blocking=False):
            raise ValueError("Another run is active for this project")
        try:
            return self._execute(plan, source, client, max_workers, max_retries, apply, parent_node)
        finally:
            project_lock.release()

    def _execute(self, plan, source, client, max_workers, max_retries, apply, parent_node):
        run_id = "run_" + uuid.uuid4().hex
        run_dir = self.state_root / "runs" / run_id
        repo = run_dir / "repo"
        repo.mkdir(parents=True)
        baseline = {}
        for name, path in source_files(source):
            content = path.read_bytes()
            baseline[name] = digest(content)
            destination = workspace_path(repo, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        self.git(repo, "init")
        self.git(repo, "config", "user.name", "Causa Runtime")
        self.git(repo, "config", "user.email", "runtime@causa.local")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "--allow-empty", "-m", "Snapshot source workspace")
        base_commit = self.git(repo, "rev-parse", "HEAD")
        root_node = self.record(run_id, "runtime", CausalNodeType.PROMPT_STEP,
            commit=base_commit, worktree=repo, prompt=plan.goal, metadata={"source": str(source)})
        if parent_node:
            self.storage.insert_edge(CausalEdge(id="edge_" + uuid.uuid4().hex,
                from_node_id=parent_node, to_node_id=root_node, type=CausalEdgeType.BRANCHED_FROM))
        manager = WorktreeManager(str(repo), str(run_dir / "worktrees"))
        integration_lock = threading.RLock()
        board = Blackboard(storage=self.storage)
        checkpoints = {}
        total_cost = [0.0]

        def worker(task):
            agent = run_id + "_" + task.id
            result = {"subtaskId": task.id, "agentName": task.title, "model": task.assigned_model,
                      "status": "FAILED", "tokens": 0, "cost_usd": 0.0,
                      "filePath": task.target_files[0], "dependencies": task.dependencies}
            with integration_lock:
                ok, error, tree = manager.create_worktree(agent)
            if not ok:
                result["error"] = error
                return result
            parent = self.record(run_id, agent, CausalNodeType.AGENT_SPAWN,
                                 parent=root_node, commit=tree.base_commit, worktree=tree.worktree_path)
            for dep in task.dependencies:
                self.storage.insert_edge(CausalEdge(id="edge_" + uuid.uuid4().hex,
                    from_node_id=checkpoints[dep], to_node_id=parent, type=CausalEdgeType.CAUSED_BY))
            candidate_board = Blackboard()
            ferry = FerryProxy(workspace_root=tree.worktree_path, blackboard=candidate_board)
            ferry.register_manifest(AgentCapabilityManifest(agent_id=agent,
                                      allowed_write_patterns=task.target_files))
            try:
                if client is None:
                    raise RuntimeError("No model provider configured")
                tier = {"frontier_heavy": GeminiTier.WORKER, "local_slm": GeminiTier.NANO}.get(
                    task.assigned_tier.value, GeminiTier.FAST)
                for relative in task.target_files:
                    previous = ""
                    feedback = ""
                    for attempt in range(max_retries + 1):
                        context = collect_context(tree.worktree_path, task.target_files)
                        prompt = task.description
                        if feedback:
                            prompt += f"\nPrevious candidate:\n{previous}\nVerification failure:\n{feedback}\nRepair this failure."
                        parent = self.record(run_id, agent, CausalNodeType.PROMPT_STEP, parent=parent,
                            commit=tree.base_commit, worktree=tree.worktree_path,
                            prompt=json.dumps({"task": prompt, "files": context, "target": relative}),
                            metadata={"inputs": {name: digest(text.encode()) for name, text in context.items()}})
                        generated = client.generate_code(task_description=prompt, file_path=relative,
                            tier=tier, context=task.synthesized_context, existing_repo_files=context)
                        result["tokens"] += generated.total_tokens
                        result["cost_usd"] += generated.cost_usd
                        result["model"] = generated.model
                        if not generated.success or not generated.response_text.strip():
                            raise RuntimeError(generated.error or "Provider returned empty output")
                        previous = generated.response_text
                        written = ferry.intercept_tool_call(agent, "write_file",
                            {"path": relative, "content": previous}, session_id=run_id, parent_node_id=parent)
                        evidence = verify_files(tree.worktree_path, [relative], run_tests=False) if written.success else None
                        if evidence and evidence.passed:
                            parent = self.record(run_id, agent, CausalNodeType.FILE_MUTATION,
                                parent=parent, worktree=tree.worktree_path,
                                metadata={"file": relative, "sha256": digest(previous.encode())})
                            break
                        feedback = evidence.log if evidence else written.error_message
                    else:
                        raise RuntimeError("Source validation failed: " + feedback)
                evidence = verify_files(tree.worktree_path, task.target_files)
                parent = self.record(run_id, agent, CausalNodeType.TEST_RUN,
                    status="success" if evidence.passed else "failed", parent=parent,
                    worktree=tree.worktree_path, metadata={"level": evidence.level, "log": evidence.log})
                if not evidence.passed:
                    raise RuntimeError(evidence.log)
                committed, error = manager.commit_worktree(agent, "Implement " + task.title)
                if not committed:
                    raise RuntimeError(error)
                with integration_lock:
                    # Commit candidate integration only after checking the combined tree.
                    try:
                        self.git(repo, "merge", "--no-commit", "--no-ff", tree.branch_name)
                        combined = verify_files(repo, task.target_files)
                        if not combined.passed:
                            raise RuntimeError("Integrated verification failed: " + combined.log)
                        self.git(repo, "commit", "--allow-empty", "-m", "Integrate " + task.title)
                    except Exception:
                        if (repo / ".git" / "MERGE_HEAD").exists():
                            self.git(repo, "merge", "--abort")
                        raise
                    commit = self.git(repo, "rev-parse", "HEAD")
                    for relative in task.target_files:
                        content = workspace_path(repo, relative).read_text(encoding="utf-8")
                        board.publish_symbols(ASTInspector.extract_symbols(content, relative), relative, agent)
                    result.update(status="COMPLETED", verificationLevel=combined.level,
                                  verificationLog=combined.log, commit=commit,
                                  generatedCode=workspace_path(repo, task.target_files[0]).read_text(encoding="utf-8"))
                    result["causalNodeId"] = self.record(run_id, agent, CausalNodeType.FILE_MUTATION,
                        parent=parent, commit=commit, worktree=repo, metadata={"result": result})
                    checkpoints[task.id] = result["causalNodeId"]
            except Exception as exc:
                result["error"] = str(exc)
                result["causalNodeId"] = self.record(run_id, agent, CausalNodeType.TEST_RUN,
                    status="failed", parent=parent, worktree=tree.worktree_path, metadata={"error": str(exc)})
            finally:
                with integration_lock:
                    total_cost[0] += result["cost_usd"]
            return result

        scheduler = SwarmSupervisor.__new__(SwarmSupervisor)
        scheduler.on_event = None
        results = scheduler.run_plan(plan, worker, max_workers=max_workers)
        success = bool(results) and all(r["status"] == "COMPLETED" for r in results)
        changed = self.git(repo, "diff", "--name-only", base_commit, "HEAD").splitlines()
        applied = False
        error = None
        if success and apply:
            try:
                current = {name: digest(path.read_bytes()) for name, path in source_files(source)}
                if current != baseline:
                    raise RuntimeError("Source changed during execution; results retained without overwriting it")
                originals = {name: workspace_path(source, name).read_bytes()
                             if workspace_path(source, name).exists() else None for name in changed}
                try:
                    for name in changed:
                        destination = workspace_path(source, name)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        temporary = destination.with_name(destination.name + ".causa-" + uuid.uuid4().hex)
                        try:
                            temporary.write_bytes(workspace_path(repo, name).read_bytes())
                            os.replace(temporary, destination)
                        finally:
                            if temporary.exists():
                                temporary.unlink()
                except Exception:
                    for name, content in originals.items():
                        destination = workspace_path(source, name)
                        if content is None:
                            destination.unlink(missing_ok=True)
                        else:
                            destination.write_bytes(content)
                    raise
                applied = True
            except Exception as exc:
                success, error = False, str(exc)
        output = {"success": success, "applied": applied, "runId": run_id, "results": results,
                  "total_tokens": sum(r.get("tokens", 0) for r in results),
                  "total_cost_usd": total_cost[0], "workspace": str(repo), "source": str(source),
                  "baseCommit": base_commit, "headCommit": self.git(repo, "rev-parse", "HEAD"),
                  "diff": self.git(repo, "diff", base_commit, "HEAD"), "error": error}
        (run_dir / "result.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        return output
