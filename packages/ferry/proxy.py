"""Ferry Transparent Tool Proxy & Pre-Commit Gateway.

Intercepts agent tool invocations (write_file, edit_file, read_file, execute_command)
before filesystem modification to enforce:
1. Capability Manifest & Path Boundaries.
2. Deterministic Read/Write Leases (via LockManager).
3. Dry-Run AST Syntax Validation (via ASTInspector).
4. Semantic Interface Diffing & Blackboard Publishing (via Blackboard).
5. Transactional Recording into Fullerence Causal DAG Substrate.
"""

import fnmatch
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from packages.ferry.lock_manager import LockManager, LeaseLockType
from packages.ferry.ast_diff import ASTInspector, ASTDiff
from packages.ferry.blackboard import Blackboard, BlackboardEntry

try:
    from packages.fullerence.types import (
        CausalNode,
        CausalNodeType,
        ToolCallIntent,
        InterceptionDecision,
        InterceptionEvaluation,
    )
except Exception:
    class CausalNodeType:
        TOOL_CALL = "tool_call"
        FILE_MUTATION = "file_mutation"

    class InterceptionDecision:
        ALLOWED = "allowed"
        BLOCKED = "blocked"

    class CausalNode(BaseModel):
        id: str
        session_id: str
        agent_id: str
        type: str
        tool_name: Optional[str] = None
        tool_payload: Optional[str] = None
        status: str = "success"
        metadata: Optional[str] = None
        created_at: int = Field(default_factory=lambda: int(time.time()))


class AgentCapabilityManifest(BaseModel):
    """Defines what files and tools an agent is authorized to access."""
    agent_id: str
    allowed_tools: List[str] = Field(default_factory=lambda: ["write_file", "edit_file", "read_file", "execute_command"])
    allowed_write_patterns: List[str] = Field(default_factory=lambda: ["*"])  # Glob patterns e.g. ["src/auth/*"]
    disallowed_write_patterns: List[str] = Field(default_factory=list)        # E.g. [".env", "config/secrets.json"]
    max_line_changes: int = 1000


class ToolExecutionResult(BaseModel):
    """Returned back to agent or caller after Ferry interception."""
    success: bool
    decision: str  # "allowed" or "blocked"
    output: Any = None
    error_message: Optional[str] = None
    ast_diffs: List[Dict[str, Any]] = Field(default_factory=list)
    causal_node_id: Optional[str] = None


class FerryProxy:
    """The central transport interceptor sitting between agents and the host system."""

    def __init__(
        self,
        lock_manager: Optional[LockManager] = None,
        blackboard: Optional[Blackboard] = None,
        ingress_gateway: Optional[Any] = None,
        workspace_root: str = "",
    ) -> None:
        self.lock_manager = lock_manager or LockManager()
        self.blackboard = blackboard or Blackboard()
        self.ingress = ingress_gateway
        self.workspace_root = workspace_root or os.getcwd()
        
        # agent_id -> AgentCapabilityManifest
        self._manifests: Dict[str, AgentCapabilityManifest] = {}

    # -------------------------------------------------------------
    # 1. Capability Manifest Registration
    # -------------------------------------------------------------
    def register_manifest(self, manifest: AgentCapabilityManifest) -> None:
        """Assigns security capability boundaries to an agent."""
        self._manifests[manifest.agent_id] = manifest

    def get_manifest(self, agent_id: str) -> AgentCapabilityManifest:
        """Retrieves manifest, defaulting to permissive if unregistered."""
        return self._manifests.get(
            agent_id,
            AgentCapabilityManifest(agent_id=agent_id),
        )

    # -------------------------------------------------------------
    # 2. Main Tool Interception Entrypoint
    # -------------------------------------------------------------
    def intercept_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        tool_payload: Dict[str, Any],
        session_id: str = "default_session",
        parent_node_id: Optional[str] = None,
    ) -> ToolExecutionResult:
        """Intercepts an agent tool call, executes the pre-commit pipeline,
        and records the decision into Fullerence.
        """
        manifest = self.get_manifest(agent_id)
        node_id = f"node_{uuid.uuid4().hex[:10]}"

        # Step A: Validate Allowed Tool
        if tool_name not in manifest.allowed_tools:
            err = f"Security Violation: Agent '{agent_id}' is not authorized to invoke tool '{tool_name}'"
            self._log_causal_step(node_id, session_id, agent_id, tool_name, tool_payload, "blocked", err)
            return ToolExecutionResult(
                success=False,
                decision="blocked",
                error_message=err,
                causal_node_id=node_id,
            )

        # Step B: Route to specialized handlers
        if tool_name in ("write_file", "edit_file"):
            return self._handle_write_file(
                node_id=node_id,
                session_id=session_id,
                agent_id=agent_id,
                tool_name=tool_name,
                payload=tool_payload,
                manifest=manifest,
            )
        elif tool_name == "read_file":
            return self._handle_read_file(
                node_id=node_id,
                session_id=session_id,
                agent_id=agent_id,
                tool_name=tool_name,
                payload=tool_payload,
            )
        elif tool_name == "execute_command":
            return self._handle_execute_command(
                node_id=node_id,
                session_id=session_id,
                agent_id=agent_id,
                payload=tool_payload,
            )
        else:
            # Generic pass-through
            self._log_causal_step(node_id, session_id, agent_id, tool_name, tool_payload, "success")
            return ToolExecutionResult(
                success=True,
                decision="allowed",
                output=f"Executed tool {tool_name}",
                causal_node_id=node_id,
            )

    # -------------------------------------------------------------
    # 3. Handler: write_file / edit_file (Pre-Commit Pipeline)
    # -------------------------------------------------------------
    def _handle_write_file(
        self,
        node_id: str,
        session_id: str,
        agent_id: str,
        tool_name: str,
        payload: Dict[str, Any],
        manifest: AgentCapabilityManifest,
    ) -> ToolExecutionResult:
        rel_path = payload.get("path") or payload.get("file_path", "")
        new_content = payload.get("content", "")
        if not rel_path:
            return ToolExecutionResult(success=False, decision="blocked", error_message="Missing 'path' parameter")

        norm_path = rel_path.replace("\\", "/").strip().lstrip("./")

        # 1. Boundary & Manifest Checks
        allowed = any(fnmatch.fnmatch(norm_path, pat) for pat in manifest.allowed_write_patterns)
        disallowed = any(fnmatch.fnmatch(norm_path, pat) for pat in manifest.disallowed_write_patterns)

        if not allowed or disallowed:
            err = f"Security Violation: Agent '{agent_id}' is restricted from modifying '{norm_path}'"
            self._log_causal_step(node_id, session_id, agent_id, tool_name, payload, "blocked", err)
            return ToolExecutionResult(success=False, decision="blocked", error_message=err, causal_node_id=node_id)

        # 2. Acquire Exclusive Write Lease
        acquired, reason, lease = self.lock_manager.acquire(
            agent_id=agent_id,
            file_path=norm_path,
            lock_type=LeaseLockType.EXCLUSIVE_WRITE,
        )
        if not acquired:
            err = f"Concurrency Block: {reason}"
            self._log_causal_step(node_id, session_id, agent_id, tool_name, payload, "blocked", err)
            return ToolExecutionResult(success=False, decision="blocked", error_message=err, causal_node_id=node_id)

        try:
            # 3. Dry-Run AST Syntax Validation
            syntax_check = ASTInspector.validate_syntax(new_content, file_path=norm_path)
            if not syntax_check.is_valid:
                err = f"AST Syntax Validation Rejected: {syntax_check.error_message}"
                self._log_causal_step(node_id, session_id, agent_id, tool_name, payload, "blocked", err)
                return ToolExecutionResult(success=False, decision="blocked", error_message=err, causal_node_id=node_id)

            # 4. Read existing content for diffing
            abs_path = os.path.join(self.workspace_root, norm_path) if self.workspace_root else norm_path
            old_content = ""
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                except Exception:
                    old_content = ""

            # 5. Extract AST Diffs
            diffs = ASTInspector.compute_ast_diffs(
                before_code=old_content,
                after_code=new_content,
                file_path=norm_path,
                causal_node_id=node_id,
            )

            # 6. Commit write to disk
            os.makedirs(os.path.dirname(abs_path), exist_ok=True) if os.path.dirname(abs_path) else None
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 7. Publish extracted interface contracts to Blackboard
            symbols = ASTInspector.extract_symbols(new_content, file_path=norm_path)
            self.blackboard.publish_symbols(symbols, file_path=norm_path, agent_id=agent_id)

            # 8. Record successful causal node
            diff_dicts = [d.model_dump() if hasattr(d, "model_dump") else d.__dict__ for d in diffs]
            self._log_causal_step(
                node_id,
                session_id,
                agent_id,
                tool_name,
                payload,
                status="success",
                metadata=json.dumps({"diffs_count": len(diffs), "path": norm_path}),
            )

            return ToolExecutionResult(
                success=True,
                decision="allowed",
                output=f"Successfully committed '{norm_path}' ({len(new_content)} bytes)",
                ast_diffs=diff_dicts,
                causal_node_id=node_id,
            )

        finally:
            # Release lease upon transaction finish
            self.lock_manager.release(agent_id=agent_id, file_path=norm_path)

    # -------------------------------------------------------------
    # 4. Handler: read_file
    # -------------------------------------------------------------
    def _handle_read_file(
        self,
        node_id: str,
        session_id: str,
        agent_id: str,
        tool_name: str,
        payload: Dict[str, Any],
    ) -> ToolExecutionResult:
        rel_path = payload.get("path") or payload.get("file_path", "")
        norm_path = rel_path.replace("\\", "/").strip().lstrip("./")

        # Acquire shared read lease
        self.lock_manager.acquire(agent_id, norm_path, lock_type=LeaseLockType.SHARED_READ)
        try:
            abs_path = os.path.join(self.workspace_root, norm_path) if self.workspace_root else norm_path
            if not os.path.exists(abs_path):
                return ToolExecutionResult(success=False, decision="blocked", error_message=f"File not found: {norm_path}")

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            self._log_causal_step(node_id, session_id, agent_id, tool_name, payload, "success")
            return ToolExecutionResult(
                success=True,
                decision="allowed",
                output=content,
                causal_node_id=node_id,
            )
        finally:
            self.lock_manager.release(agent_id, norm_path)

    # -------------------------------------------------------------
    # 5. Handler: execute_command
    # -------------------------------------------------------------
    def _handle_execute_command(
        self,
        node_id: str,
        session_id: str,
        agent_id: str,
        payload: Dict[str, Any],
    ) -> ToolExecutionResult:
        command = payload.get("command", "")
        # Basic interception check (e.g. prevent rm -rf /)
        dangerous_patterns = ["rm -rf", "format c:", "del /s /q c:"]
        if any(p in command.lower() for p in dangerous_patterns):
            err = f"Security Violation: Rejected dangerous command '{command}'"
            self._log_causal_step(node_id, session_id, agent_id, "execute_command", payload, "blocked", err)
            return ToolExecutionResult(success=False, decision="blocked", error_message=err, causal_node_id=node_id)

        self._log_causal_step(node_id, session_id, agent_id, "execute_command", payload, "success")
        return ToolExecutionResult(
            success=True,
            decision="allowed",
            output=f"Command '{command}' permitted by Ferry",
            causal_node_id=node_id,
        )

    # -------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------
    def _log_causal_step(
        self,
        node_id: str,
        session_id: str,
        agent_id: str,
        tool_name: str,
        payload: Dict[str, Any],
        status: str,
        metadata: Optional[str] = None,
    ) -> None:
        """Records the intercepted event into Fullerence Ingress if attached."""
        if self.ingress and hasattr(self.ingress, "record_tool_call_intent"):
            try:
                intent = ToolCallIntent(
                    session_id=session_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    tool_payload=json.dumps(payload),
                )
                self.ingress.record_tool_call_intent(intent)
            except Exception:
                pass
