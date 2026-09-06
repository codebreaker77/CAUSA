"""Causa / Fullerence Substrate Data Types and Pydantic Models."""

import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Enums
# -------------------------------------------------------------
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
    CAUSED_BY = "caused_by"             # Step T -> Step T-1
    MUTATED_AST = "mutated_ast"         # Tool call -> Static AST Symbol Node
    READ_BLACKBOARD = "read_blackboard" # Agent read AST exported by peer agent
    TAINTED_BY = "tainted_by"           # Downstream dependency on unverified step
    BRANCHED_FROM = "branched_from"     # Counterfactual execution fork


class ASTDiffType(str, Enum):
    SIGNATURE_CHANGED = "signature_changed"
    ADDED_EXPORT = "added_export"
    DELETED_EXPORT = "deleted_export"
    BODY_CHANGED = "body_changed"


class LeaseLockState(str, Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"
    BLOCKED = "blocked"


class InterceptionDecision(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PAUSED_ON_BREAKPOINT = "paused_on_breakpoint"


class PreCommitRuleType(str, Enum):
    DISALLOW_BREAKING_SIGNATURES = "disallow_breaking_signatures"
    MAX_LINES_DELETED = "max_lines_deleted"
    ENFORCE_FILE_LEASE = "enforce_file_lease"
    CUSTOM_POLICY = "custom_policy"


# -------------------------------------------------------------
# Causal Graph Models
# -------------------------------------------------------------
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
    status: str = Field("success", description="Status: success, committed, failed, faulty, blocked")
    metadata: Optional[str] = Field(None, description="Extra metadata / diagnostic notes")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class CausalEdge(BaseModel):
    id: str = Field(..., description="Unique edge UUID")
    from_node_id: str = Field(..., description="Source node ID")
    to_node_id: str = Field(..., description="Target node ID")
    type: CausalEdgeType = Field(..., description="Causal relationship type")
    metadata: Optional[str] = Field(None, description="Diagnostic payload")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class ASTDiff(BaseModel):
    id: str = Field(..., description="Diff UUID")
    causal_node_id: str = Field(..., description="Linked causal node ID")
    file_path: str = Field(..., description="Target file path")
    diff_type: ASTDiffType = Field(..., description="Type of AST change")
    symbol_id: str = Field(..., description="Qualified symbol name (e.g., func_login)")
    before_signature: Optional[str] = Field(None, description="Contract signature before change")
    after_signature: Optional[str] = Field(None, description="Contract signature after change")
    raw_diff: Optional[str] = Field(None, description="Unified line diff")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp in seconds")


class Lease(BaseModel):
    id: str = Field(..., description="Lease UUID")
    agent_id: str = Field(..., description="Agent holding the lock")
    file_path: str = Field(..., description="Repository relative file path")
    lock_state: LeaseLockState = Field(LeaseLockState.ACQUIRED, description="Lock state")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="Acquisition timestamp")


class BlackboardEntry(BaseModel):
    id: str = Field(..., description="Blackboard entry UUID")
    symbol_id: str = Field(..., description="Symbol identifier")
    name: str = Field(..., description="Function/class name")
    signature: str = Field(..., description="Full contract signature")
    file_path: str = Field(..., description="File where symbol is defined")
    agent_id: str = Field(..., description="Agent that owns/exported the symbol")
    updated_at: int = Field(default_factory=lambda: int(time.time()), description="Update timestamp")


# -------------------------------------------------------------
# Ingress & Interception Models
# -------------------------------------------------------------
class ToolCallIntent(BaseModel):
    session_id: str
    agent_id: str
    tool_name: str
    tool_payload: str
    worktree_path: Optional[str] = None
    git_commit_hash: Optional[str] = None
    parent_node_id: Optional[str] = None


class PreCommitRule(BaseModel):
    rule_id: str
    rule_type: PreCommitRuleType
    max_line_deletions: int = 50
    enforce_on_symbols: Optional[List[str]] = None
    description: str = ""


class InterceptionEvaluation(BaseModel):
    decision: InterceptionDecision
    allowed: bool
    violated_rules: List[str] = Field(default_factory=list)
    hit_breakpoint_id: Optional[str] = None
    reason: str = "All pre-commit semantic checks passed."
    suggested_remedy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------
# Semantic Breakpoint Models
# -------------------------------------------------------------
class SemanticBreakpoint(BaseModel):
    id: str
    condition_type: str  # 'ast_diff', 'status_failure', 'tool_match', 'custom'
    target_symbol: Optional[str] = None
    target_tool: Optional[str] = None
    expected_status: Optional[str] = None
    description: str = ""


class BreakpointManager:
    """Evaluates causal execution events against registered semantic breakpoints."""

    def __init__(self) -> None:
        self.breakpoints: Dict[str, SemanticBreakpoint] = {}

    def add_breakpoint(self, bp: SemanticBreakpoint) -> None:
        self.breakpoints[bp.id] = bp

    def remove_breakpoint(self, bp_id: str) -> None:
        self.breakpoints.pop(bp_id, None)

    def evaluate(
        self,
        node: CausalNode,
        diffs: Optional[List[ASTDiff]] = None,
    ) -> Optional[SemanticBreakpoint]:
        for bp in self.breakpoints.values():
            if bp.condition_type == "status_failure" and node.status in ("failed", "error"):
                return bp
            if bp.condition_type == "tool_match" and bp.target_tool and node.tool_name == bp.target_tool:
                return bp
            if bp.condition_type == "ast_diff" and diffs:
                for d in diffs:
                    if bp.target_symbol and d.symbol_id == bp.target_symbol:
                        return bp
                    if d.diff_type in ("signature_changed", "contract_broken"):
                        return bp
        return None

