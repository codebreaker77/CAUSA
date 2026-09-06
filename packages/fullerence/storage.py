"""SQLite persistence and zero-loss snapshot store for Causa Fullerence layer."""

import os
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from packages.core.db.models import (
    Base,
    CausalNodeModel,
    CausalEdgeModel,
    ASTDiffModel,
    LeaseModel,
    BlackboardModel,
)
from packages.core.schemas.nodes import (
    CausalNode,
    CausalEdge,
    ASTDiff,
    Lease,
    BlackboardEntry,
)


class FullerenceStorage:
    """Manages SQLite storage for the Causa relational causal DAG."""

    def __init__(self, db_path: str = "causa.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # Performance pragmas: WAL mode, synchronous=NORMAL, foreign_keys=ON
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode = WAL;"))
            conn.execute(text("PRAGMA synchronous = NORMAL;"))
            conn.execute(text("PRAGMA foreign_keys = ON;"))
            conn.commit()

        # Create tables
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    # -------------------------------------------------------------
    # Causal Nodes
    # -------------------------------------------------------------
    def insert_node(self, node: CausalNode) -> CausalNode:
        with self.get_session() as session:
            model = CausalNodeModel(
                id=node.id,
                session_id=node.session_id,
                agent_id=node.agent_id,
                worktree_path=node.worktree_path,
                git_commit_hash=node.git_commit_hash,
                parent_node_id=node.parent_node_id,
                prompt_hash=node.prompt_hash,
                prompt_snapshot=node.prompt_snapshot,
                tool_name=node.tool_name,
                tool_payload=node.tool_payload,
                type=node.type.value if hasattr(node.type, "value") else str(node.type),
                status=node.status,
                metadata_json=node.metadata,
                created_at=node.created_at,
            )
            session.merge(model)
            session.commit()
            return node

    def get_node(self, node_id: str) -> Optional[CausalNode]:
        with self.get_session() as session:
            m = session.query(CausalNodeModel).filter_by(id=node_id).first()
            if not m:
                return None
            return CausalNode(
                id=m.id,
                session_id=m.session_id,
                agent_id=m.agent_id,
                worktree_path=m.worktree_path,
                git_commit_hash=m.git_commit_hash,
                parent_node_id=m.parent_node_id,
                prompt_hash=m.prompt_hash,
                prompt_snapshot=m.prompt_snapshot,
                tool_name=m.tool_name,
                tool_payload=m.tool_payload,
                type=m.type,
                status=m.status,
                metadata=m.metadata_json,
                created_at=m.created_at,
            )

    def get_session_nodes(self, session_id: str) -> List[CausalNode]:
        with self.get_session() as session:
            models = (
                session.query(CausalNodeModel)
                .filter_by(session_id=session_id)
                .order_by(CausalNodeModel.created_at.asc())
                .all()
            )
            return [
                CausalNode(
                    id=m.id,
                    session_id=m.session_id,
                    agent_id=m.agent_id,
                    worktree_path=m.worktree_path,
                    git_commit_hash=m.git_commit_hash,
                    parent_node_id=m.parent_node_id,
                    prompt_hash=m.prompt_hash,
                    prompt_snapshot=m.prompt_snapshot,
                    tool_name=m.tool_name,
                    tool_payload=m.tool_payload,
                    type=m.type,
                    status=m.status,
                    metadata=m.metadata_json,
                    created_at=m.created_at,
                )
                for m in models
            ]

    # -------------------------------------------------------------
    # Causal Edges
    # -------------------------------------------------------------
    def insert_edge(self, edge: CausalEdge) -> CausalEdge:
        with self.get_session() as session:
            model = CausalEdgeModel(
                id=edge.id,
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                type=edge.type.value if hasattr(edge.type, "value") else str(edge.type),
                metadata_json=edge.metadata,
                created_at=edge.created_at,
            )
            session.merge(model)
            session.commit()
            return edge

    def get_outgoing_edges(self, from_node_id: str) -> List[CausalEdge]:
        with self.get_session() as session:
            models = session.query(CausalEdgeModel).filter_by(from_node_id=from_node_id).all()
            return [
                CausalEdge(
                    id=m.id,
                    from_node_id=m.from_node_id,
                    to_node_id=m.to_node_id,
                    type=m.type,
                    metadata=m.metadata_json,
                    created_at=m.created_at,
                )
                for m in models
            ]

    def get_incoming_edges(self, to_node_id: str) -> List[CausalEdge]:
        with self.get_session() as session:
            models = session.query(CausalEdgeModel).filter_by(to_node_id=to_node_id).all()
            return [
                CausalEdge(
                    id=m.id,
                    from_node_id=m.from_node_id,
                    to_node_id=m.to_node_id,
                    type=m.type,
                    metadata=m.metadata_json,
                    created_at=m.created_at,
                )
                for m in models
            ]

    # -------------------------------------------------------------
    # AST Diffs
    # -------------------------------------------------------------
    def insert_ast_diff(self, diff: ASTDiff) -> ASTDiff:
        with self.get_session() as session:
            model = ASTDiffModel(
                id=diff.id,
                causal_node_id=diff.causal_node_id,
                file_path=diff.file_path,
                diff_type=diff.diff_type.value if hasattr(diff.diff_type, "value") else str(diff.diff_type),
                symbol_id=diff.symbol_id,
                before_signature=diff.before_signature,
                after_signature=diff.after_signature,
                raw_diff=diff.raw_diff,
                created_at=diff.created_at,
            )
            session.merge(model)
            session.commit()
            return diff

    def get_node_ast_diffs(self, causal_node_id: str) -> List[ASTDiff]:
        with self.get_session() as session:
            models = session.query(ASTDiffModel).filter_by(causal_node_id=causal_node_id).all()
            return [
                ASTDiff(
                    id=m.id,
                    causal_node_id=m.causal_node_id,
                    file_path=m.file_path,
                    diff_type=m.diff_type,
                    symbol_id=m.symbol_id,
                    before_signature=m.before_signature,
                    after_signature=m.after_signature,
                    raw_diff=m.raw_diff,
                    created_at=m.created_at,
                )
                for m in models
            ]

    # -------------------------------------------------------------
    # Leases
    # -------------------------------------------------------------
    def record_lease(self, lease: Lease) -> Lease:
        with self.get_session() as session:
            model = LeaseModel(
                id=lease.id,
                agent_id=lease.agent_id,
                file_path=lease.file_path,
                lock_state=lease.lock_state.value if hasattr(lease.lock_state, "value") else str(lease.lock_state),
                timestamp=lease.timestamp,
            )
            session.merge(model)
            session.commit()
            return lease

    def get_active_lease(self, file_path: str) -> Optional[Lease]:
        with self.get_session() as session:
            m = (
                session.query(LeaseModel)
                .filter_by(file_path=file_path)
                .order_by(LeaseModel.timestamp.desc())
                .first()
            )
            if m and m.lock_state == "acquired":
                return Lease(
                    id=m.id,
                    agent_id=m.agent_id,
                    file_path=m.file_path,
                    lock_state=m.lock_state,
                    timestamp=m.timestamp,
                )
            return None

    # -------------------------------------------------------------
    # Blackboard
    # -------------------------------------------------------------
    def update_blackboard(self, entry: BlackboardEntry) -> BlackboardEntry:
        with self.get_session() as session:
            model = BlackboardModel(
                id=entry.id,
                symbol_id=entry.symbol_id,
                name=entry.name,
                signature=entry.signature,
                file_path=entry.file_path,
                agent_id=entry.agent_id,
                updated_at=entry.updated_at,
            )
            session.merge(model)
            session.commit()
            return entry

    def get_blackboard(self) -> List[BlackboardEntry]:
        with self.get_session() as session:
            models = session.query(BlackboardModel).order_by(BlackboardModel.updated_at.desc()).all()
            return [
                BlackboardEntry(
                    id=m.id,
                    symbol_id=m.symbol_id,
                    name=m.name,
                    signature=m.signature,
                    file_path=m.file_path,
                    agent_id=m.agent_id,
                    updated_at=m.updated_at,
                )
                for m in models
            ]
