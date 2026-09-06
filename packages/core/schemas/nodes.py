"""Pydantic schemas for Causa DAG nodes, edges, leases, and AST diffs."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import time


class CausalNodeType(str, Enum):
    AGENT_SPAWN = "agent_spawn"
    PROMPT_STEP = "prompt_step"
    TOOL_CALL = "tool_call"
    FILE_MUTATION = "file_mutation"
    TERMINAL_EXEC = "terminal_exec"
    TEST_RUN = "test_run"
    BREAKPOINT_HIT = "breakpoint_hit"
    ROLLBACK_EVENT = "rollback_event"


class CausalEdgeType(str, Enum):
    CAUSED_BY = "caused_by"           # Step T -> Step T-1
    MUTATED_AST = "mutated_ast"       # Tool call -> Static AST Symbol Node
    READ_BLACKBOARD = "read_blackboard" # Agent read AST exported by peer agent
    TAINTED_BY = "tainted_by"         # Downstream dependency on unverified step
    BRANCHED_FROM = "branched_from"   # Counterfactual execution fork


class ASTDiffType(str, Enum):
    SIGNATURE_CHANGED = "signature_changed"
    ADDED_EXPORT = "added_export"
    DELETED_EXPORT = "deleted_export"
    BODY_CHANGED = "body_changed"


class LeaseLockState(str, Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"
    BLOCKED = "blocked"


class CausalNode(BaseModel):
    id: str = Field(..., description="Unique step UUID")
    session_id: str = Field(..., description="Overall Causa session ID")
    agent_id: str = Field(..., description="Identifier of the subagent")
    type: CausalNodeType = Field(..., description="Type of causal event")
    worktree_path: Optional[str] = Field(None, description="Path to isolated Git worktree")
    git_commit_hash: Optional[str] = Field(None, description="Git commit hash at this step")
    parent_node_id: Optional[str] = Field(None, description="Direct predecessor node ID in DAG")
    prompt_hash: Optional[str] = Field(None, description="SHA-256 hash of context tokens")
    prompt_snapshot: Optional[str] = Field(None, description="Exact prompt and context tokens at step T")
    tool_name: Optional[str] = Field(None, description="Name of tool invoked (e.g. writeFile, bash)")
    tool_payload: Optional[str] = Field(None, description="JSON serialized payload or command")
    status: str = Field("success", description="Status: success, failed, faulty, blocked")
    metadata: Optional[str] = Field(None, description="Extra metadata / diagnostic notes")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class CausalEdge(BaseModel):
    id: str = Field(..., description="Unique edge UUID")
    from_node_id: str = Field(..., description="Source node ID")
    to_node_id: str = Field(..., description="Target node ID")
    type: CausalEdgeType = Field(..., description="Type of causal relationship")
    metadata: Optional[str] = Field(None, description="Associated symbol or edge notes")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class ASTDiff(BaseModel):
    id: str = Field(..., description="Unique AST diff UUID")
    causal_node_id: str = Field(..., description="Node where mutation occurred")
    file_path: str = Field(..., description="Target file path")
    diff_type: ASTDiffType = Field(..., description="Classification of AST change")
    symbol_id: Optional[str] = Field(None, description="ID of AST symbol affected")
    before_signature: Optional[str] = Field(None, description="Interface signature before edit")
    after_signature: Optional[str] = Field(None, description="Interface signature after edit")
    raw_diff: Optional[str] = Field(None, description="Unified or structural diff")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class Lease(BaseModel):
    id: str = Field(..., description="Unique lease record UUID")
    agent_id: str = Field(..., description="Agent claiming or releasing the lease")
    file_path: str = Field(..., description="Path to leased file")
    lock_state: LeaseLockState = Field(..., description="Lock state")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class BlackboardEntry(BaseModel):
    id: str = Field(..., description="Unique blackboard entry UUID")
    symbol_id: Optional[str] = Field(None, description="ID of exported AST symbol")
    name: str = Field(..., description="Function/class/interface name")
    signature: Optional[str] = Field(None, description="Full type signature")
    file_path: str = Field(..., description="File exporting the interface")
    agent_id: str = Field(..., description="Agent that published the export")
    updated_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")
