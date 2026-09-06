"""Dual-layer Causal DAG and AST Knowledge Substrate powered by NetworkX."""

from typing import Dict, List, Optional, Set, Any
import networkx as nx

from packages.fullerence.types import (
    CausalNode,
    CausalEdge,
    CausalEdgeType,
    CausalNodeType,
    ASTDiff,
)
from packages.fullerence.storage import FullerenceStorage


class FullerenceGraph:
    """In-memory NetworkX directed acyclic graph synchronized with SQLite storage."""

    def __init__(self, storage: FullerenceStorage):
        self.storage = storage
        self.dag = nx.DiGraph()

    def sync_from_storage(self, session_id: str) -> None:
        """Loads all nodes and edges for a session into the NetworkX graph."""
        nodes = self.storage.get_session_nodes(session_id)
        for node in nodes:
            self.dag.add_node(
                node.id,
                session_id=node.session_id,
                agent_id=node.agent_id,
                type=node.type.value if hasattr(node.type, "value") else str(node.type),
                worktree_path=node.worktree_path,
                git_commit_hash=node.git_commit_hash,
                prompt_hash=node.prompt_hash,
                prompt_snapshot=node.prompt_snapshot,
                tool_name=node.tool_name,
                tool_payload=node.tool_payload,
                status=node.status,
                created_at=node.created_at,
            )

        # Ingest all outgoing edges for loaded nodes
        for node in nodes:
            outgoing = self.storage.get_outgoing_edges(node.id)
            for edge in outgoing:
                self.dag.add_edge(
                    edge.from_node_id,
                    edge.to_node_id,
                    id=edge.id,
                    type=edge.type.value if hasattr(edge.type, "value") else str(edge.type),
                    metadata=edge.metadata,
                )

    def add_node(self, node: CausalNode) -> None:
        """Inserts a node into both SQLite and the in-memory NetworkX DAG."""
        self.storage.insert_node(node)
        self.dag.add_node(
            node.id,
            session_id=node.session_id,
            agent_id=node.agent_id,
            type=node.type.value if hasattr(node.type, "value") else str(node.type),
            worktree_path=node.worktree_path,
            git_commit_hash=node.git_commit_hash,
            prompt_hash=node.prompt_hash,
            prompt_snapshot=node.prompt_snapshot,
            tool_name=node.tool_name,
            tool_payload=node.tool_payload,
            status=node.status,
            created_at=node.created_at,
        )

    def add_edge(self, edge: CausalEdge) -> None:
        """Inserts an edge into both SQLite and the in-memory NetworkX DAG."""
        self.storage.insert_edge(edge)
        self.dag.add_edge(
            edge.from_node_id,
            edge.to_node_id,
            id=edge.id,
            type=edge.type.value if hasattr(edge.type, "value") else str(edge.type),
            metadata=edge.metadata,
        )

    def get_ancestors(self, node_id: str) -> Set[str]:
        """Returns all ancestor node IDs in the causal graph."""
        if node_id not in self.dag:
            return set()
        return nx.ancestors(self.dag, node_id)

    def get_descendants(self, node_id: str) -> Set[str]:
        """Returns all descendant node IDs (forward reachable taint set)."""
        if node_id not in self.dag:
            return set()
        return nx.descendants(self.dag, node_id)
