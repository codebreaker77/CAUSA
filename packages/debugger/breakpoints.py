"""Semantic Breakpoints Evaluator for Causal Execution."""

from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
from packages.core.schemas.nodes import CausalNode, ASTDiff


class SemanticBreakpoint(BaseModel):
    """Rule specifying when execution should pause or break."""
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
        """Checks if a causal node or its associated AST diffs trigger any breakpoint."""
        for bp in self.breakpoints.values():
            # 1. Breakpoint on failed test or status error
            if bp.condition_type == "status_failure" and node.status in ("failed", "error"):
                return bp

            # 2. Breakpoint on specific tool execution
            if bp.condition_type == "tool_match" and bp.target_tool and node.tool_name == bp.target_tool:
                return bp

            # 3. Breakpoint on semantic AST mutation (e.g., breaking signature change)
            if bp.condition_type == "ast_diff" and diffs:
                for d in diffs:
                    if bp.target_symbol and d.symbol_id == bp.target_symbol:
                        return bp
                    if d.diff_type in ("signature_changed", "contract_broken"):
                        return bp

        return None
