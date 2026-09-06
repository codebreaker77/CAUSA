"""Schemas for in-flight interception, tool call intents, and pre-commit AST rules."""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class InterceptionDecision(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PAUSED_ON_BREAKPOINT = "paused_on_breakpoint"


class PreCommitRuleType(str, Enum):
    DISALLOW_BREAKING_SIGNATURES = "disallow_breaking_signatures"
    MAX_LINES_DELETED = "max_lines_deleted"
    ENFORCE_FILE_LEASE = "enforce_file_lease"
    CUSTOM_POLICY = "custom_policy"


class PreCommitRule(BaseModel):
    """Configuration for a pre-commit semantic guardrail."""
    rule_id: str
    rule_type: PreCommitRuleType
    max_line_deletions: int = 50
    enforce_on_symbols: Optional[List[str]] = None
    description: str = ""


class InterceptionEvaluation(BaseModel):
    """Result of evaluating a proposed tool mutation against pre-commit AST rules."""
    decision: InterceptionDecision
    allowed: bool
    violated_rules: List[str] = Field(default_factory=list)
    hit_breakpoint_id: Optional[str] = None
    reason: str = "All pre-commit semantic checks passed."
    suggested_remedy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCallIntent(BaseModel):
    """Payload representing an intended tool execution before filesystem commit."""
    session_id: str
    agent_id: str
    tool_name: str
    tool_payload: str
    worktree_path: Optional[str] = None
    git_commit_hash: Optional[str] = None
    parent_node_id: Optional[str] = None
