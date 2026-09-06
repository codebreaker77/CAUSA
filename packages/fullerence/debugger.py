"""Causal Debugger engine integrated into Fullerence substrate."""

from typing import Dict, Any, List, Set, Optional
from sqlalchemy import text
from packages.fullerence.types import (
    CausalNode,
    ASTDiff,
    SemanticBreakpoint,
    BreakpointManager,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph


# -------------------------------------------------------------
# 1. Semantic Breakpoint Evaluator
# -------------------------------------------------------------
# BreakpointManager and SemanticBreakpoint are imported from packages.fullerence.types


# -------------------------------------------------------------
# 2. First-Bad-Decision Localization
# -------------------------------------------------------------
def localize_first_bad_decision(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    failure_node_id: str,
) -> Dict[str, Any]:
    """Traverses backward from a failure node to find the earliest diverging contract mutation."""
    from packages.debugger.localization import localize_first_bad_decision as _loc
    return _loc(storage, graph, failure_node_id)


# -------------------------------------------------------------
# 3. Transitive Taint Invalidation & Blast Radius
# -------------------------------------------------------------
def get_transitive_taint_set(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    corrupt_node_id: str,
) -> Dict[str, Any]:
    """Computes all downstream nodes, agents, worktrees, and files tainted by a corrupt node."""
    from packages.debugger.invalidation import get_transitive_taint_set as _taint
    return _taint(storage, graph, corrupt_node_id)


def compute_counterfactual_fork_point(
    storage: FullerenceStorage,
    graph: FullerenceGraph,
    corrupt_node_id: str,
) -> Dict[str, Any]:
    """Calculates clean ancestor commit, target worktree, and git reset rollback plan."""
    from packages.debugger.invalidation import compute_counterfactual_fork_point as _fork
    return _fork(storage, graph, corrupt_node_id)


# -------------------------------------------------------------
# 4. Token Context Attribution View
# -------------------------------------------------------------
def get_attribution_view(
    storage: FullerenceStorage,
    node_id: str,
) -> Dict[str, Any]:
    """Deconstructs the context window of a step into categorized attribution slices."""
    from packages.debugger.attribution import get_attribution_view as _attr
    return _attr(storage, node_id)


# -------------------------------------------------------------
# 5. CausalDebugger Service Wrapper
# -------------------------------------------------------------
class CausalDebugger:
    """Unified debugger service over Fullerence substrate."""

    def __init__(self, storage: FullerenceStorage, graph: Optional[FullerenceGraph] = None) -> None:
        self.storage = storage
        self.graph = graph or FullerenceGraph(storage)
        self.breakpoints = BreakpointManager()

    def blame(self, failure_node_id: str) -> Dict[str, Any]:
        """Pinpoints root-cause agent and breaking AST change."""
        return localize_first_bad_decision(self.storage, self.graph, failure_node_id)

    def get_blast_radius(self, corrupt_node_id: str) -> Dict[str, Any]:
        """Calculates transitive taint across agents, worktrees, and files."""
        return get_transitive_taint_set(self.storage, self.graph, corrupt_node_id)

    def plan_rollback(self, corrupt_node_id: str) -> Dict[str, Any]:
        """Computes clean checkpoint and executable git reset command."""
        return compute_counterfactual_fork_point(self.storage, self.graph, corrupt_node_id)

    def inspect_attribution(self, node_id: str) -> Dict[str, Any]:
        """Returns categorized context slices explaining LLM reasoning."""
        return get_attribution_view(self.storage, node_id)
