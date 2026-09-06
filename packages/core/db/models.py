"""SQLAlchemy database models for Causa DAG, leases, diffs, and blackboard."""

from sqlalchemy import Column, String, Integer, Text, Index
from sqlalchemy.orm import declarative_base
import time

Base = declarative_base()


class CausalNodeModel(Base):
    __tablename__ = "causal_nodes"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    worktree_path = Column(String, nullable=True)
    git_commit_hash = Column(String, nullable=True, index=True)
    parent_node_id = Column(String, nullable=True, index=True)
    prompt_hash = Column(String, nullable=True)
    prompt_snapshot = Column(Text, nullable=True)
    tool_name = Column(String, nullable=True)
    tool_payload = Column(Text, nullable=True)
    type = Column(String, nullable=False, index=True)
    status = Column(String, default="success")
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(Integer, default=lambda: int(time.time()), index=True)


class CausalEdgeModel(Base):
    __tablename__ = "causal_edges"

    id = Column(String, primary_key=True)
    from_node_id = Column(String, nullable=False, index=True)
    to_node_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(Integer, default=lambda: int(time.time()))


class ASTDiffModel(Base):
    __tablename__ = "ast_diffs"

    id = Column(String, primary_key=True)
    causal_node_id = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    diff_type = Column(String, nullable=False)
    symbol_id = Column(String, nullable=True, index=True)
    before_signature = Column(Text, nullable=True)
    after_signature = Column(Text, nullable=True)
    raw_diff = Column(Text, nullable=True)
    created_at = Column(Integer, default=lambda: int(time.time()))


class LeaseModel(Base):
    __tablename__ = "leases_log"

    id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    lock_state = Column(String, nullable=False)
    timestamp = Column(Integer, default=lambda: int(time.time()), index=True)


class BlackboardModel(Base):
    __tablename__ = "blackboard"

    id = Column(String, primary_key=True)
    symbol_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    signature = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    agent_id = Column(String, nullable=False, index=True)
    updated_at = Column(Integer, default=lambda: int(time.time()), index=True)
