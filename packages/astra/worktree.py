"""Astra Git Worktree Sandbox Manager.

Provides physical filesystem sandboxing for heterogeneous coding agents using
lightweight Git worktrees. Guarantees zero-collision execution:
1. Worktree Provisioning: Creates an isolated directory under .causa/worktrees/<agent_id>
   branching off a clean base commit.
2. Status & Diff Inspection: Computes uncommitted changes, staged diffs, and commit logs
   isolated to the agent's worktree.
3. Automated Verification Gate: Runs test commands strictly inside the sandbox.
4. Atomic Merge & Teardown: Executes safe 3-way merges into the target branch or cleanly
   prunes and removes the sandbox on failure/completion.
"""

import os
import shutil
import subprocess
import time
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class WorktreeMetadata(BaseModel):
    agent_id: str
    branch_name: str
    worktree_path: str
    base_commit: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    status: str = "active"  # "active", "merged", "aborted", "cleaned"


class WorktreeManager:
    """Manages the creation, lifecycle, verification, and teardown of Git worktrees."""

    def __init__(self, repo_root: str = "", worktrees_dir: str = "") -> None:
        self.repo_root = os.path.abspath(repo_root or os.getcwd())
        self.worktrees_dir = os.path.abspath(
            worktrees_dir or os.path.join(self.repo_root, ".causa", "worktrees")
        )
        os.makedirs(self.worktrees_dir, exist_ok=True)
        
        # agent_id -> WorktreeMetadata
        self._worktrees: Dict[str, WorktreeMetadata] = {}

    # -------------------------------------------------------------
    # 1. Provision Worktree
    # -------------------------------------------------------------
    def create_worktree(
        self,
        agent_id: str,
        base_branch: str = "HEAD",
        branch_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[WorktreeMetadata]]:
        """Provisions a new isolated Git worktree for an agent.
        
        Returns:
            (success: bool, error_message: Optional[str], metadata: Optional[WorktreeMetadata])
        """
        clean_agent_id = agent_id.replace("/", "_").replace("\\", "_")
        target_branch = branch_name or f"causa/agent/{clean_agent_id}_{int(time.time())}"
        worktree_path = os.path.join(self.worktrees_dir, clean_agent_id)

        # If worktree already exists, clean it up first
        if os.path.exists(worktree_path):
            self.remove_worktree(clean_agent_id, force=True)

        # Get current commit hash of base_branch
        code, commit_hash, err = self._run_git(["rev-parse", base_branch])
        if code != 0 or not commit_hash:
            return False, f"Failed to resolve base ref '{base_branch}': {err}", None

        # Execute: git worktree add -b <branch> <path> <base_commit>
        cmd = ["worktree", "add", "-b", target_branch, worktree_path, commit_hash.strip()]
        code, out, err = self._run_git(cmd)
        if code != 0:
            return False, f"Git worktree creation failed: {err or out}", None

        meta = WorktreeMetadata(
            agent_id=clean_agent_id,
            branch_name=target_branch,
            worktree_path=worktree_path,
            base_commit=commit_hash.strip(),
        )
        self._worktrees[clean_agent_id] = meta
        return True, None, meta

    # -------------------------------------------------------------
    # 2. Status & Diffs
    # -------------------------------------------------------------
    def get_worktree_diff(self, agent_id: str) -> str:
        """Returns the uncommitted git diff inside the agent's worktree."""
        meta = self.get_worktree(agent_id)
        if not meta or not os.path.exists(meta.worktree_path):
            return ""

        code, out, _ = self._run_git(["diff", "HEAD"], cwd=meta.worktree_path)
        return out if code == 0 else ""

    def get_branch_diff(self, agent_id: str, target_branch: str = "main") -> str:
        """Returns full diff between the agent's branch and target branch."""
        meta = self.get_worktree(agent_id)
        if not meta:
            return ""

        code, out, _ = self._run_git(["diff", f"{target_branch}...{meta.branch_name}"])
        return out if code == 0 else ""

    # -------------------------------------------------------------
    # 3. Verification Gate (Run Tests in Sandbox)
    # -------------------------------------------------------------
    def run_verification(
        self,
        agent_id: str,
        command: str,
        timeout_seconds: int = 60,
    ) -> Tuple[bool, str]:
        """Runs a validation command (e.g. pytest or npm test) inside the agent's worktree."""
        meta = self.get_worktree(agent_id)
        if not meta or not os.path.exists(meta.worktree_path):
            return False, f"Worktree for agent '{agent_id}' does not exist"

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=meta.worktree_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = proc.stdout + "\n" + proc.stderr
            return (proc.returncode == 0), output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Verification command timed out after {timeout_seconds}s"
        except Exception as err:
            return False, f"Verification failed with exception: {str(err)}"

    # -------------------------------------------------------------
    # 4. Commit Changes in Sandbox
    # -------------------------------------------------------------
    def commit_worktree(
        self,
        agent_id: str,
        commit_message: str,
        author_name: str = "Causa Agent",
    ) -> Tuple[bool, Optional[str]]:
        """Stages all changes and commits them within the agent's worktree."""
        meta = self.get_worktree(agent_id)
        if not meta or not os.path.exists(meta.worktree_path):
            return False, "Worktree does not exist"

        # Stage all changes
        code, _, err = self._run_git(["add", "-A"], cwd=meta.worktree_path)
        if code != 0:
            return False, f"Failed to stage changes: {err}"

        # Commit
        code, out, err = self._run_git(
            ["commit", "-m", commit_message, f"--author={author_name} <agent@causa.local>"],
            cwd=meta.worktree_path,
        )
        if code != 0:
            # Maybe nothing to commit
            if "nothing to commit" in (out + err):
                return True, "Nothing to commit"
            return False, f"Git commit failed: {err or out}"

        return True, None

    # -------------------------------------------------------------
    # 5. Merge Worktree into Target Branch
    # -------------------------------------------------------------
    def merge_worktree(
        self,
        agent_id: str,
        target_branch: str = "main",
    ) -> Tuple[bool, Optional[str]]:
        """Merges the agent's worktree branch into the target branch."""
        meta = self.get_worktree(agent_id)
        if not meta:
            return False, f"Unknown worktree for agent '{agent_id}'"

        # Ensure all worktree changes are committed first
        self.commit_worktree(agent_id, f"auto-commit before merge: {agent_id}")

        # Checkout target branch in repo_root
        code, _, err = self._run_git(["checkout", target_branch])
        if code != 0:
            return False, f"Failed to checkout target branch '{target_branch}': {err}"

        # Merge agent branch
        code, out, err = self._run_git(["merge", "--no-ff", "-m", f"Merge agent {agent_id} into {target_branch}", meta.branch_name])
        if code != 0:
            # Merge conflict occurred -> abort merge
            self._run_git(["merge", "--abort"])
            return False, f"Merge conflict occurred when merging '{meta.branch_name}' into '{target_branch}': {err or out}"

        meta.status = "merged"
        return True, None

    # -------------------------------------------------------------
    # 6. Teardown & Cleanup
    # -------------------------------------------------------------
    def remove_worktree(self, agent_id: str, force: bool = True) -> bool:
        """Removes the worktree and cleans up the corresponding branch."""
        clean_agent_id = agent_id.replace("/", "_").replace("\\", "_")
        meta = self._worktrees.get(clean_agent_id)
        worktree_path = meta.worktree_path if meta else os.path.join(self.worktrees_dir, clean_agent_id)

        if os.path.exists(worktree_path):
            args = ["worktree", "remove", worktree_path]
            if force:
                args.append("--force")
            code, _, _ = self._run_git(args)
            if code != 0:
                # Fallback to direct directory removal
                shutil.rmtree(worktree_path, ignore_errors=True)
                self._run_git(["worktree", "prune"])

        # Delete branch if exists
        if meta and meta.branch_name:
            self._run_git(["branch", "-D", meta.branch_name])
            meta.status = "cleaned"

        if clean_agent_id in self._worktrees:
            del self._worktrees[clean_agent_id]

        return True

    def get_worktree(self, agent_id: str) -> Optional[WorktreeMetadata]:
        """Returns metadata for an agent's active worktree."""
        return self._worktrees.get(agent_id.replace("/", "_").replace("\\", "_"))

    def list_worktrees(self) -> List[WorktreeMetadata]:
        """Lists all active worktrees tracked by Astra."""
        return list(self._worktrees.values())

    # -------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------
    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Executes a git command with UTF-8 decoding."""
        cmd = ["git"] + args
        working_dir = cwd or self.repo_root
        try:
            proc = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except Exception as err:
            return 1, "", str(err)
