"""Fullerence Causal Substrate, Graph Engine, Debugger, Ingress, Daemon, CLI & MCP."""

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
    BreakpointManager,
    SemanticBreakpoint,
)
from packages.fullerence.models import (
    Base,
    CausalNodeModel,
    CausalEdgeModel,
    ASTDiffModel,
    LeaseModel,
    BlackboardModel,
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
)
from packages.fullerence.daemon import (
    WorktreeWatcher,
    BlackboardSynchronizer,
    MultiWorktreeDaemon,
    WorktreeDaemon,
)
from packages.fullerence.mcp import FullerenceMCPServer, CausaMCPServer
from packages.fullerence.cli import (
    cmd_log,
    cmd_blame,
    cmd_rollback,
    cmd_inspect,
    main as cli_main,
)

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
    "BreakpointManager",
    "SemanticBreakpoint",
    # Database Models
    "Base",
    "CausalNodeModel",
    "CausalEdgeModel",
    "ASTDiffModel",
    "LeaseModel",
    "BlackboardModel",
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
    # Daemon & Watcher
    "WorktreeWatcher",
    "BlackboardSynchronizer",
    "MultiWorktreeDaemon",
    "WorktreeDaemon",
    # Agent MCP
    "FullerenceMCPServer",
    "CausaMCPServer",
    # CLI
    "cmd_log",
    "cmd_blame",
    "cmd_rollback",
    "cmd_inspect",
    "cli_main",
]
