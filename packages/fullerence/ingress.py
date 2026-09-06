"""Transport & Ingestion Interception Gateway for Causa."""

import time
import uuid
from typing import Dict, Any, List, Optional
from packages.fullerence.types import (
    CausalNode,
    CausalNodeType,
    CausalEdge,
    CausalEdgeType,
    ASTDiff,
    ASTDiffType,
    BlackboardEntry,
    ToolCallIntent,
    PreCommitRule,
    PreCommitRuleType,
    InterceptionDecision,
    InterceptionEvaluation,
    BreakpointManager,
)
from packages.fullerence.models import (
    CausalNodeModel,
    CausalEdgeModel,
    ASTDiffModel,
    BlackboardModel,
)
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph


class IngressGateway:
    """Gateway intercepting agent tool mutations before filesystem writes."""

    def __init__(self, storage: FullerenceStorage, graph: FullerenceGraph) -> None:
        self.storage = storage
        self.graph = graph

    # -------------------------------------------------------------
    # 1. Record Tool Call Intent (In-Flight)
    # -------------------------------------------------------------
    def record_tool_call_intent(self, intent: ToolCallIntent) -> CausalNode:
        """Logs an intended tool action before filesystem modification."""
        node_id = f"intent_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)

        node = CausalNode(
            id=node_id,
            session_id=intent.session_id,
            agent_id=intent.agent_id,
            worktree_path=intent.worktree_path,
            git_commit_hash=intent.git_commit_hash,
            parent_node_id=intent.parent_node_id,
            tool_name=intent.tool_name,
            tool_payload=intent.tool_payload,
            type=CausalNodeType.TOOL_CALL,
            status="pending_interception",
            created_at=now,
        )

        # Persist intent node to SQLite
        self.storage.insert_node(node)
        self.graph.add_node(node)

        # Connect causal chain from parent
        if intent.parent_node_id:
            edge = CausalEdge(
                id=f"e_{uuid.uuid4().hex[:8]}",
                from_node_id=intent.parent_node_id,
                to_node_id=node.id,
                type=CausalEdgeType.CAUSED_BY,
                created_at=now,
            )
            self.storage.insert_edge(edge)
            self.graph.add_edge(edge)

        return node

    # -------------------------------------------------------------
    # 2. Evaluate Semantic Breakpoints & Pre-Commit Rules
    # -------------------------------------------------------------
    def evaluate_semantic_breakpoints(
        self,
        node: CausalNode,
        ast_diffs: List[ASTDiff],
        rules: List[PreCommitRule],
        breakpoint_mgr: Optional[BreakpointManager] = None,
    ) -> InterceptionEvaluation:
        """Evaluates pre-commit AST rules and semantic breakpoints on candidate diffs."""
        # 1. Check registered semantic breakpoints first
        if breakpoint_mgr:
            hit = breakpoint_mgr.evaluate(node, diffs=ast_diffs)
            if hit:
                return InterceptionEvaluation(
                    decision=InterceptionDecision.PAUSED_ON_BREAKPOINT,
                    allowed=False,
                    hit_breakpoint_id=hit.id,
                    reason=f"Execution paused: Semantic breakpoint '{hit.id}' triggered. ({hit.description})",
                    suggested_remedy="Inspect AST diff before proceeding or resume debugger.",
                    metadata={"target_symbol": hit.target_symbol},
                )

        violated_rules: List[str] = []
        remedies: List[str] = []

        for rule in rules:
            # Rule A: Disallow Breaking Exported Signatures
            if rule.rule_type == PreCommitRuleType.DISALLOW_BREAKING_SIGNATURES:
                for diff in ast_diffs:
                    if diff.diff_type == ASTDiffType.SIGNATURE_CHANGED:
                        # Check symbol enforcement target if specified
                        if not rule.enforce_on_symbols or diff.symbol_id in rule.enforce_on_symbols:
                            violated_rules.append(rule.rule_id)
                            remedies.append(
                                f"Symbol contract '{diff.symbol_id}' changed from '{diff.before_signature}' "
                                f"to '{diff.after_signature}'. Preserve backwards compatibility or provide default arguments."
                            )

            # Rule B: Max Lines Deleted Guard
            elif rule.rule_type == PreCommitRuleType.MAX_LINES_DELETED:
                for diff in ast_diffs:
                    if diff.raw_diff:
                        deleted_lines = [
                            line for line in diff.raw_diff.splitlines()
                            if line.startswith("-") and not line.startswith("---")
                        ]
                        if len(deleted_lines) > rule.max_line_deletions:
                            violated_rules.append(rule.rule_id)
                            remedies.append(
                                f"Mutation deletes {len(deleted_lines)} lines in {diff.file_path}, "
                                f"exceeding threshold of {rule.max_line_deletions} lines."
                            )

            # Rule C: Enforce File Leases
            elif rule.rule_type == PreCommitRuleType.ENFORCE_FILE_LEASE:
                for diff in ast_diffs:
                    active_lease = self.storage.get_active_lease(diff.file_path)
                    if active_lease and active_lease.agent_id != node.agent_id:
                        violated_rules.append(rule.rule_id)
                        remedies.append(
                            f"File '{diff.file_path}' is actively leased by agent '{active_lease.agent_id}'."
                        )

        if violated_rules:
            return InterceptionEvaluation(
                decision=InterceptionDecision.BLOCKED,
                allowed=False,
                violated_rules=violated_rules,
                reason="Pre-commit AST semantic rule violation.",
                suggested_remedy="; ".join(remedies),
            )

        return InterceptionEvaluation(
            decision=InterceptionDecision.ALLOWED,
            allowed=True,
            reason="All pre-commit semantic checks passed.",
        )

    # -------------------------------------------------------------
    # 3. Commit Causal Step (Atomic SQLite Transaction)
    # -------------------------------------------------------------
    def commit_causal_step(
        self,
        node_id: str,
        status: str,
        ast_diffs: Optional[List[ASTDiff]] = None,
        edges: Optional[List[CausalEdge]] = None,
        blackboard_entries: Optional[List[BlackboardEntry]] = None,
    ) -> CausalNode:
        """Atomically persists the causal node state, AST diffs, and edges to SQLite."""
        with self.storage.get_session() as session:
            # 1. Update node status
            m_node = session.query(CausalNodeModel).filter_by(id=node_id).first()
            if not m_node:
                raise ValueError(f"Causal node {node_id} not found to commit.")
            m_node.status = status

            # 2. Insert AST diffs
            if ast_diffs:
                for diff in ast_diffs:
                    m_diff = ASTDiffModel(
                        id=diff.id,
                        causal_node_id=node_id,
                        file_path=diff.file_path,
                        diff_type=diff.diff_type.value if hasattr(diff.diff_type, "value") else str(diff.diff_type),
                        symbol_id=diff.symbol_id,
                        before_signature=diff.before_signature,
                        after_signature=diff.after_signature,
                        raw_diff=diff.raw_diff,
                        created_at=diff.created_at,
                    )
                    session.merge(m_diff)

            # 3. Insert Causal Edges
            if edges:
                for edge in edges:
                    m_edge = CausalEdgeModel(
                        id=edge.id,
                        from_node_id=edge.from_node_id,
                        to_node_id=edge.to_node_id,
                        type=edge.type.value if hasattr(edge.type, "value") else str(edge.type),
                        metadata_json=edge.metadata,
                        created_at=edge.created_at,
                    )
                    session.merge(m_edge)

            # 4. Update Shared Blackboard
            if blackboard_entries:
                for entry in blackboard_entries:
                    m_bb = BlackboardModel(
                        id=entry.id,
                        symbol_id=entry.symbol_id,
                        name=entry.name,
                        signature=entry.signature,
                        file_path=entry.file_path,
                        agent_id=entry.agent_id,
                        updated_at=entry.updated_at,
                    )
                    session.merge(m_bb)

            session.commit()

        # Update in-memory graph
        updated_node = self.storage.get_node(node_id)
        if updated_node:
            self.graph.add_node(updated_node)
            if edges:
                for edge in edges:
                    self.graph.add_edge(edge)
            return updated_node

        raise RuntimeError(f"Failed to retrieve committed node: {node_id}")
