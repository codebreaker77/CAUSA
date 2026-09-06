"""SQLAlchemy database models for Fullerence SQLite WAL storage."""

import time
from sqlalchemy import Column, String, Integer, Text, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CausalNodeModel(Base):
    __tablename__ = "causal_nodes"

    id = Column(String, primary_key=True)
    session_id = Column(String, index=True, nullable=False)
    agent_id = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    worktree_path = Column(String, nullable=True)
    git_commit_hash = Column(String, nullable=True)
    parent_node_id = Column(String, nullable=True)
    prompt_hash = Column(String, nullable=True)
    prompt_snapshot = Column(Text, nullable=True)
    tool_name = Column(String, nullable=True)
    tool_payload = Column(Text, nullable=True)
    status = Column(String, default="success", nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)


class CausalEdgeModel(Base):
    __tablename__ = "causal_edges"

    id = Column(String, primary_key=True)
    from_node_id = Column(String, index=True, nullable=False)
    to_node_id = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)


class ASTDiffModel(Base):
    __tablename__ = "ast_diffs"

    id = Column(String, primary_key=True)
    causal_node_id = Column(String, index=True, nullable=False)
    file_path = Column(String, index=True, nullable=False)
    diff_type = Column(String, nullable=False)
    symbol_id = Column(String, index=True, nullable=False)
    before_signature = Column(Text, nullable=True)
    after_signature = Column(Text, nullable=True)
    raw_diff = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)


class LeaseModel(Base):
    __tablename__ = "leases_log"

    id = Column(String, primary_key=True)
    agent_id = Column(String, index=True, nullable=False)
    file_path = Column(String, index=True, nullable=False)
    lock_state = Column(String, nullable=False)
    timestamp = Column(BigInteger, default=lambda: int(time.time()), nullable=False)


class BlackboardModel(Base):
    __tablename__ = "blackboard_events"

    id = Column(String, primary_key=True)
    symbol_id = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    signature = Column(Text, nullable=False)
    file_path = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    updated_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)
