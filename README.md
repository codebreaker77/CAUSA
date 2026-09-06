# CAUSA

> **Distributed Systems Control Plane, Transparent Transport Interceptor, and Time-Travel Debugger for Multi-Agent Coding Swarms.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)

---

## Executive Summary & Core Thesis

Modern AI coding agents operate as **amnesiac, uncoordinated distributed processes** that frequently degrade codebases through:
1. **Silent Context Poisoning**: Agents ingest obsolete, hallucinated, or irrelevant files, polluting their reasoning context.
2. **Unrecoverable Bad Decisions**: Multi-turn errors compound uncontrollably down an append-only linear transcript, burning tokens and requiring full restarts.
3. **Multi-Agent File Collisions**: Concurrently running agents overwrite each other's code, introduce conflicting interfaces, and trigger catastrophic Git merge conflicts.

Existing multi-agent frameworks treat execution as an **append-only chat transcript**. When scaling to swarms of heterogeneous agents, this paradigm breaks down.

**Causa resolves this by conceptualizing a multi-agent coding swarm as a debuggable distributed program.**

Causa acts as a local control plane, transparent transport interceptor, and distributed systems debugger. Rather than replacing the internal reasoning loops of coding agents, Causa instruments their system interactions (process I/O, MCP calls, and filesystem mutations) to provide **causal transparency**, **deterministic concurrency protection**, and **counterfactual time-travel execution**.

`
                               +------------------------+
                               |    DEVELOPER PROMPT    |
                               +-----------+------------+
                                           |
                                           v
+----------------------------------------------------------------------------------------+
|                                       CAUSA                                            |
|                                                                                        |
|  +-----------------------+   +------------------------+   +-------------------------+  |
|  |         ASTRA         |   |         FERRY          |   |       FULLERENCE        |
|  | Swarm & Process       |   | Transport Interceptor  |   | Dual-Layer Causal &     |
|  | Orchestrator          |   | & Pre-Commit Gate      |   | AST Knowledge Substrate |
|  +----------+------------+   +-----------+------------+   +------------+------------+  |
|             |                            |                             |               |
|             +----------------------------+-----------------------------+               |
|                                          |                                             |
|                                          v                                             |
|                              +------------------------+                                |
|                              |        DEBUGGER        |                                |
|                              | Time-Travel & Causal   |                                |
|                              | Invalidation Engine    |                                |
|                              +-----------+------------+                                |
+------------------------------------------+---------------------------------------------+
                                           | WebSocket Telemetry
                                           v
                               +------------------------+
                               |   CAUSA VISUAL UI      |
                               |  DAG Flight Recorder   |
                               +------------------------+
`

---

## System Architecture

Causa is composed of five tightly integrated pillars:

### 1. Astra - Heterogeneous Process & Swarm Orchestrator
Astra manages OS-level processes for any CLI-driven or MCP-compliant agent.
- **Task Ingestion & High-Level Planning**: Decomposes top-level goals into dependency-directed subtask graphs.
- **Model Routing & Scoping (Local SLM)**: Employs an on-device Small Language Model (Qwen2.5-Coder / Phi-3) to evaluate task complexity and assign tasks across model tiers (Frontier Heavy, Fast Cloud, or Local SLM).
- **AST Context Synthesis**: Synthesizes typed skeletons and interface stubs from dependencies, pruning context tokens by up to 90%.
- **Worktree Sandboxing**: Every spawned subagent runs in a strictly isolated Git worktree (.causa/worktrees/<agent-id>), preventing filesystem collisions.
- **Intercepted PTY Process Launch**: Spawns agent CLIs via pseudo-terminals (PTY) with transparent proxy routing through Ferry.
- **Lifecycle Governance**: Maintains actor state machines (IDLE -> RUNNING -> BLOCKED -> DONE / FAILED).
- **Automated Verification & Atomic Merge**: Runs test validation inside the worktree before executing atomic 3-way merges into the parent branch.

### 2. Ferry - Transport Interceptor & Pre-Commit Engine
Ferry acts as an active, inline security and synchronization gateway between agents and the host system.
- **Transparent Interception**: Proxies MCP JSON-RPC protocol calls and terminal stdio streams in real time.
- **ACL & Capability Enforcement**: Validates every file mutation and tool call against the agent's assigned Capability Manifest.
- **Deterministic Pre-Commit Locking**: Manages read/write leases per file to eliminate race conditions and dirty writes across concurrent agents.
- **Dry-Run Lint & Syntax Validation**: Performs AST-level parsing before allowing any write operation to touch disk.
- **AST Diff Extraction**: Analyzes tree-sitter ASTs to isolate structural interface changes (classes, methods, type signatures) from internal logic changes.
- **Read-Replicated Blackboard**: Broadcasts extracted interface diffs to peer agents through a low-latency SQLite blackboard (WAL mode).

### 3. Fullerence - Dual-Layer Causal & AST Knowledge Substrate
Fullerence provides the underlying persistent relational graph connecting agent actions to codebase reality.
- **Relational Causal DAG**: Records every prompt, decision, MCP invocation, file mutation, and verification step as a typed node in a directed acyclic graph.
- **Zero-Loss State Persistence**: Stores the complete context window, token attribution, and prompt state at every discrete step T.
- **AST Interface Graph**: Maps symbols, interfaces, and file dependencies directly against the causal action nodes that introduced or modified them.
- **Multi-Worktree Daemon**: Continuously synchronizes Git commit hashes and file diffs across all active agent worktrees.

### 4. Debugger - Distributed Flight Recorder & Time-Travel Engine
The core diagnostic brain of Causa, applying classical distributed systems debugging primitives to AI swarms.
- **Causal Breakpoints**: Halts execution across single or multiple agents when semantic conditions, AST breaking changes, or test failure thresholds trigger.
- **First-Bad-Decision Localization**: Traverses the Fullerence DAG backward from a symptom (e.g. broken build) to identify the root incorrect assumption.
- **Token Context Attribution**: Shows exact file lines, terminal outputs, and blackboard events active in the context window at any step.
- **Transitive Causal Invalidation**: When an agent's decision is rolled back, the debugger automatically discovers and marks all downstream dependent agents as tainted, invalidating or rolling back their states.
- **Counterfactual Execution**: Rewinds the filesystem and Git worktree to an uncorrupted ancestor node and branches forward with modified constraints or alternative models.

### 5. Frontend - Visual Flight Recorder & Inspector
A reactive Next.js 14 web application providing deep observability into swarm behavior.
- **Interactive Causal DAG View**: Built with React Flow, color-coding nodes by health, failure, taint, or rollback state.
- **Active Playback Bar**: Step-indexed scrubber allowing developers to scrub backward and forward through swarm execution history.
- **Token Consumption Metrics**: Live token burn, memory footprint, and monetary cost tracking broken down per model tier.
- **Graph Forking & Node Surgery**: Direct UI controls to delete poisoned nodes, edit prompt parameters, and fork alternative execution branches.
- **Shared Blackboard Feed**: Real-time stream of broadcasted AST diffs and interface contracts.
- **SLM Inspection Panel**: Live visibility into why the local SLM selected specific models and assigned specific file bounds.

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend Core** | Python 3.11+ / asyncio | High-performance async runtime with rich OS/PTY primitives |
| **API Server** | FastAPI + WebSockets | Sub-millisecond real-time event streaming to the UI |
| **Database** | SQLite (WAL mode) + SQLAlchemy | Zero-configuration, high-concurrency local storage |
| **DAG Computation** | NetworkX | Robust graph traversal algorithms for causal analysis |
| **Process Sandboxing** | pexpect / pty + Git Worktrees | Zero filesystem collisions, universal CLI agent compatibility |
| **AST Parsing** | Tree-sitter / Python ast | Language-agnostic semantic interface diff extraction |
| **Local SLM** | Ollama (qwen2.5-coder:7b / phi3:mini) | Offline, zero-cost, sub-second routing and housekeeping |
| **Frontend App** | Next.js 14 + TypeScript | Component-driven, high-performance web dashboard |
| **Graph Visualization** | React Flow | Hardware-accelerated, interactive node-link visualization |
| **UI Components** | Tailwind CSS + shadcn/ui | Modern, responsive developer-tool aesthetics |

---

## How Causa Compares

| Feature | Raw Agent Harnesses (Aider, Picode, SWE-bench) | Multi-Agent Frameworks (AutoGen, CrewAI) | Causa |
|:---|:---|:---|:---|
| **Execution Paradigm** | Linear append-only transcript | Turn-based conversational chat | **Nonlinear Causal DAG** |
| **Concurrency Safety** | None (collisions likely) | Soft prompt coordination | **Deterministic Pre-Commit Leases** |
| **Filesystem Isolation** | Shared single folder | Shared or container-based | **Per-agent Git Worktrees** |
| **Interface Awareness** | Full file injection (token heavy) | Raw string passing | **AST Skeletons & Blackboard** |
| **Failure Recovery** | Retry loop (compounding errors) | Restart session | **Counterfactual Time-Travel Rewind** |
| **Error Diagnostics** | Manual terminal log inspection | Transcript scrolling | **First-Bad-Decision Localization** |
| **Cross-Agent Bleed** | Undetected cascading errors | Silent prompt pollution | **Transitive Causal Invalidation** |

---

## Quick Start

`ash
git clone https://github.com/codebreaker77/CAUSA.git
cd CAUSA

# 1. Backend
python -m venv .venv
.venv\\Scripts\\activate
pip install fastapi uvicorn sqlalchemy networkx pexpect gitpython aiohttp websockets

# 2. Frontend
cd apps/ui
pnpm install
pnpm dev
`

---

## Authors & Contributors

- **Vismay Shrouty** ([@codebreaker77](https://github.com/codebreaker77)) - *Architecture & System Design*
