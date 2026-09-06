"""Fullerence Causal Substrate, Graph Engine, Debugger, Ingress, Daemon & MCP."""

from packages.fullerence.types import (
    CausalNode,
    CausalNodeType,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    Lease,
    LeaseLockState,
    BlackboardEntry,
    ToolCallIntent,
    PreCommitRule,
    PreCommitRuleType,
    InterceptionDecision,
    InterceptionEvaluation,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.fullerence.ingress import IngressGateway
from packages.fullerence.debugger import (
    CausalDebugger,
    localize_first_bad_decision,
    get_transitive_taint_set,
    compute_counterfactual_fork_point,
    get_attribution_view,
    BreakpointManager,
    SemanticBreakpoint,
)
from packages.fullerence.daemon import (
    WorktreeWatcher,
    BlackboardSynchronizer,
    MultiWorktreeDaemon,
    WorktreeDaemon,
)
from packages.fullerence.mcp import FullerenceMCPServer

__all__ = [
    # Types & Enums
    "CausalNode",
    "CausalNodeType",
    "CausalEdge",
    "CausalEdgeType",
    "ASTDiff",
    "ASTDiffType",
    "Lease",
    "LeaseLockState",
    "BlackboardEntry",
    "ToolCallIntent",
    "PreCommitRule",
    "PreCommitRuleType",
    "InterceptionDecision",
    "InterceptionEvaluation",
    # Substrate Core
    "FullerenceStorage",
    "FullerenceGraph",
    "IngressGateway",
    # Debugger Engine
    "CausalDebugger",
    "localize_first_bad_decision",
    "get_transitive_taint_set",
    "compute_counterfactual_fork_point",
    "get_attribution_view",
    "BreakpointManager",
    "SemanticBreakpoint",
    # Daemon & Watcher
    "WorktreeWatcher",
    "BlackboardSynchronizer",
    "MultiWorktreeDaemon",
    "WorktreeDaemon",
    # Agent MCP
    "FullerenceMCPServer",
]
