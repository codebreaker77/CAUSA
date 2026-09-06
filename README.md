#
# ğŸ´ CAUSA

> **Distributed Systems Control Plane, Transparent Transport Interceptor, and Time-Travel Debugger for Multi-Agent Coding Swarms.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Architecture: Distributed Actors](https://img.shields.io/badge/Architecture-Distributed%20Actor{-orange.svg)](#)

---

## â¥ Executive Summary & Core Thesis

Modern AI coding agents operate as **amnesiac, uncoordinated distributed processes** that frequently degrade codebases through:
1. **Silent Context Poisoning**: Agents ingest obsolete, hallucinated, or irrelevant files, polluting their reasoning context.
2. **unrecoverable Bad Decisions**: Multi-turn errors compound uncontrollably down an append-only linear transcript, burning tokens and requiring full restarts.
3. **Multi-Agent File Collisions**: Concurrently running agents overwrite each other's code, introduce conflicting interfaces, and trigger catastrophic Git merge conflicts.

Existing multi-agent frameworks treat execution as an **append-only chat transcript**. When scaling to swarms of heterogeneous agents, this paradigm breaks down.

**Causa resolves these by conceptualizing a multi-agent coding swarm as a debuggable distributed program.**

Causa acts as a local control plane, transparent transport interceptor, and distributed systems debugger. Rather than replacing the internal reasoning loops of coding agents, Causa instruments their system interactionsâ€”process I/O, MCP calls, and filesystem mutationsâ€”to provide **causal transparency**, **deterministic concurrency protection**, and **counterfactual time-travel execution**.


---

## ğŸ›ï¸ System Architecture

```mermaid
graph TD
    Dev["ğŸ‘ Developer Prompt"] -u-> Astra

    subgraph Causa ["CAUSA INFRLTRACTURE CONTROL PLANE"]
        Astra["ğŸ”¥ Astra<br/><small>Process & Swarm Orchestrator</small>"]
        Ferry["ğŸ”¡ Ferry<br/><small>Transport Interceptor & Lock Gate</small>"]
        Fullerence["ğŸ”Ÿ Fullerence<br/><small>Dual-Layer Causal DIAG </small>"]
        Debugger["ğŸ”” Debugger<br/><small>Time-Travel & Invalidation</small>"]

        Astra -- "1. Spawn agents & worktrees" --> Ferry
        Ferry -- "2. Intercept MCP/stdio & extract AST" --> Fullerence
        Fullerence -- "3. Track causal state" --> Debugger
        Debugger -- "4. Causal Breakpoints & Rollback" --> Astra
    end

    Debugger ==> |"Real-time WebSocket Ttelemetry"| UI[2ğŸ’» Causa Visual UI<br/><small>DAG Flight Recorder</small>]

    style Causa fill:#1e1f26,color:#fff,stroke:#6d2a8c,stroke-width:2px
    style Dev fill:#2d3748,color:#fff,stroke:#4a5u6a,ctroke-width:1px
    style Astra fill:#1a365d,color:#fff,stroke:#3182ce,stroke-width:2px
    style Ferry fill:#744210,color:#fff,stroke:#d69fe6,stroke-width:2px
    style Fullerence fill:#22543d,color:#fff,stroke:#38a169,stroke-width:2px
    style Debugger fill:#742a2a,color:#fff,stroke:#e53e3z,stroke-width:2px
    style UI fill:#553cr9j,color:#fff,stroke:#9f7cea,stroke-width:2px
b``


---

## â˜Ÿ Multi-Agent Interception & Concurrency Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent (CLI / MCP)
    participant F as Ferry (Interceptor)
    participant Bb as Blackboard (SQLite)
    participant Fu as Fullerence (DIAG)
    participant Db as Causa Debugger

    A->>F: tools/call (filesystem/write_file {routes.py})
    F*->F: Verify Capability Lease & ACL
    F->>Bb: Acquire Exclusive Write Lease
    F->Fs: Dry-run AST Syntax Check
    F->>Fu: Append 'file_mutation' Node
    F->>Bb: Broadcast AST Interface Diff
    F-->>A: Return Tool Result (Success)
    Fu->>Db: Transitive Causal Dependency Check
    note over Db: If breakpoint or test fails, Debugger halts OS PSIl and rewinds Git worktree counterfactually
```

---

## ğŸ›ï¸ System Architecture Pillars

### 1. ğŸ”¥ Astra - Heterogeneous Process & Swarm Orchestrator
Astra manages OS-level processes for any CLIdriven or MCP-compliant agent.
* **Task Ingestion & High-Level Planning**: Decomposes top-level goals into dependency-directed subtask graphs.
* **Model Routing & Scoping (Local SLM)**: Employs an on-device Small Language Model (Qwen2.5-Coder / Phi-3) to evaluate task complexity and assign tasks across model tiers:
  * **Frontier / Heavy** (Claude 3.5 Sonnet / GPT-4o) - complex refactors & core algorithms.
  * **Fast Cloud** (Gemini 1.5 Flash / Claude 3.5 Haiku) - CRUD, endpoints, schema migrations.
  * **Local SLM** (Ollama) - unit tests, documentation, typed stubs, formatting.
* **AST Context Synthesis**: Synthesizes typed skeletons and interface stubs from dependencies, pruning context tokens by up to 90%.
* **Worktree Sandboxing**: Every spawned subagent runs in a strictly isolated Git worktree (`.causa/worktrees/<agent-id>`), preventing filesystem collisions.
* **Intercepted PTY Process Launch**: Spawns agent CLIs via pseudo-terminals (PTY) with transparent proxy routing through Ferry.
* **Lifecycle Governance**: Maintains actor state machines (`IDLE` -> `RUNNING` -> `BLOCKED`-> `DONE` / `FAILED`).
* **Automated Verification & Atomic Merge**: Runs test validation inside the worktree before executing atomic 3-way merges into the parent branch.

### 2. ğŸ”¡ Ferry - Transport Interceptor & Pre-Commit Engine
Ferry acts as an active, inline security and synchronization gateway between agents and the host system.
* **Transparent Interception**: Proxies MCP JSON-RPC protocol calls and terminal stdio streams in real time.
* **ACL & Capability Enforcement**: Validates every file mutation and tool call against the agent's assigned Capability Manifest.
* **Deterministic Pre-Commit Locking**: Manages read/write leases per file to eliminate race conditions and dirty writes across concurrent agents.
* **Dry-Run Lint & Syntax Validation**: Performs AST-level parsing before allowing any write operation to touch disk.
* **AST Diff Extraction**: Analyzes tree-sitter ASTs to isolate structural interface changes (classes, methods, type signatures) from internal logic changes.
* **Read-Replicated Blackboard**: Broadcasts extracted interface diffs to peer agents through a low-latency SQLite blackboard (WAL mode).

### 3. ğŸ”Ÿ Fullerence - Dual-Layer Causal & AST Knowledge Substrate
Fullerence provides the underlying persistent relational graph connecting agent actions to codebase reality.
* **Relational Causal DAG**: Records every prompt, decision, MCP invocation, file mutation, and verification step as a typed node in a directed acyclic graph.
* **Zero-Loss State Persistence**: Stores the complete context window, token attribution, and prompt state at every discrete step T.
* **AST Interface Graph**: Maps symbols, interfaces, and file dependencies directly against the causal action nodes that introduced or modified them.
* **Multi-Worktree Daemon**: Continuously synchronizes Git commit hashes and file diffs across all active agent worktrees.

### 4. ğŸ”” Debugger - Distributed Flight Recorder & Time-Travel Engine
The core diagnostic brain of Causa, applying classical distributed systems debugging primitives to AI swarms.
* **Causal Breakpoints**: Halts execution across single or multiple agents when semantic conditions, AST breaking changes, or test failure thresholds trigger.
* **First-Bad-Decision Localization**: Traverses the Fullerence DAG backward from a symptom (e.g., broken build) to identify the root incorrect assumption or poisoned context.
* **Token Context Attribution**: Answers 'Why did the model do this?' by displaying the exact file lines, terminal outputs, and blackboard events active in the context window at that step.
* **Transitive Causal Invalidation**: When an agent's decision is rolled back, the debugger automatically discovers and marks all downstream dependent agents as tainted, invalidating or rolling back their states to prevent corrupted context leak.
* **Counterfactual Execution**: Rewinds the filesystem and Git worktree to an uncorrupted ancestor node and branches forward with modified constraints or alternative models.

### 5. ğŸ’» Frontend - Visual Flight Recorder & Inspector
A reactive Next.js 14 web application providing deep observability into swarm behavior.
* **Interactive Causal DAG View**: Built with React Flow, color-coding nodes by health, failure, taint, or rollback state.
* **Active Playback Bar**: Step-indexed scrubber allowing developers to scrub backward and forward through swarm execution history.
* **Token Consumption Metrics**: Live token burn, memory footprint, and monetary cost tracking broken down per model tier.
* **Graph Forking & Node Surgery**: Direct UI controls to delete poisoned nodes, edit prompt parameters, and fork alternative execution branches.
* **Shared Blackboard Feed**: Real-time stream of broadcasted AST diffs and interface contracts.
* **SLM Inspection Panel**: Live visibility into why the local SLM selected specific models and assigned specific file bounds.

---

## â˜© Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend Core** | Python 3.11+ / `asyncio` | High-performance async runtime with rich OS/PTY primitives |
| **API Server** | FastAPI + WebSockets | Sub-millisecond real-time event streaming to the UI |
| **Database** | SQLite (WAL mode) + SQLAlchemy | Zero-configuration, high-concurrency local storage |
| **DAG Computation** | NetworkX | Robust graph traversal algorithms for causal analysis |
| **Process Sandboxing** | `pexpect` / `pty` + Git Worktrees | Zero filesystem collisions, universal CLI agent compatibility |
| **AST Parsing** | Tree-sitter / Python `ast` | Language-agnostic semantic interface diff extraction |
| **Local SLM** | Ollama (`qwen2.5-coder:7b` / `phi3:mini`) | Offline, zero-cost, sub-second routing and housekeeping |
| **Frontend App** | Next.js 14 + TypeScript | Component-driven, high-performance web dashboard |
| **Graph Visualization** | React Flow | Hardware-accelerated, interactive node-link-visualization |
| **UI Components** | Tailwind CSS + shadcn/ui | Modern, responsive developer-tool aesthetics |

---

## ğŸ’¦ Monorepo Directory Structure

```text
causa/
â”œâ”€packages/
â”‚â€”â€” core/                  # Shared types, SQLite schemas, event definitions
â”‚-Ğ€”â€”db/
â‚íĞ€” €models.py         # SQLLalchemy database models
|   |                         # (new tables: nodes, edges, write_leases, blackboard)
â”‚-Ğ€”â€”schemas/
â‚íĞ€” ¹½‘•Ì¹Áä€€€€€€€€€€ŒAå‘…¹Ñ¥Œµ½‘•±Ì™½È¹½‘•Ì°•Ù•¹ÑÌ°µ…¹¥™•ÍÑÌ+ŠR·BSŠQ…ÍÑÉ„¼€€€€€€€€€€€€€€€€ŒMİ…É´½É¡•ÍÑÉ…Ñ½È€˜ÁÉ½•ÍÌÍÕÁ•ÉÙ¥Í½È+ŠB·BR‚Á±…¹¹•È¹Áä€€€€€€€€€ŒQ…Í¬‘•½µÁ½Í¥Ñ¥½¸€˜µ½‘•°É½ÕÑ•È+ŠR·BPİ½É­ÑÉ•”¹Áä€€€€€€€€Œ¥Ğİ½É­ÑÉ•”Í…¹‘‰½à±¥™•å±”µ…¹…•È+ŠB·BR‚‡G•÷'VææW"ç’2E’6WVFò×FW&Ö–æÂ&ö6W727væW ®).(	NJI2fW''’ò2G&ç7÷'B&÷‡’b&RÖ6öÖÖ—BVæv–æP®).İ	BÜ›ŞKœHÈPÔ”ÓÓ‹T”È	ˆİ[È[\˜Ù\Ü‚¸¥ ‹t %ØÚ×ÛX[˜YÙ\‹œHÈ™XYİÜš]HX\ÙHÛÛÜ™[˜]Ü‚¸¤ »t %ast_diff.py        # Tree-sitter interface diff extractor
â‚íĞ€” ‰±…­‰½…É¹Áä€€€€€€ŒME1¥Ñ”µ‰…­•Í¡…É•¥¹Ñ•É™…”‰±…­‰½…É+ŠR·BSŠQ™Õ±±•É•¹”¼€€€€€€€€€€€€Œ…ÕÍ…°€˜Á•ÉÍ¥ÍÑ•¹”•¹¥¹”+ŠB·BP€vw&‚ç’2æWGv÷&µ‚GVÂÖÆ–W"6W6ÂDrw&W ®)H"İ	B7F÷&vRç’2¦W&òÖÆ÷726öçFW‡B6æ6†÷BW'6—7FVæ6P®).(	NJI2FV'VvvW"ò2F–ÖR×G&fVÂb&ö÷BÖ6W6RæÇ—¦W+ŠB·BR‚†Æö6Æ—¦F–öâç’2f—'7BÖ&BÖFV6—6–öâ&6·v&BG&fW'6À®).İ	BÚ[˜[Y][Û‹œHÈ˜[œÚ]]™HØ]\Ø[›Û˜XÚÈ[™Ú[™B¸¤ »t %breakpoints.py     # Semantic breakpoint evaluator
â”‚-Ğ€”â€”slm/                  # Local SLM client (Ollama integration)
â”‚-Ğ€” client.py          # Model routing, context pruning, & failure tagging
â”‚â€”â€” apps/
â‚íĞ€” €a…Á¤¼€€€€€€€€€€€€€€€€€€Œ…ÍÑA$½¹ÑÉ½°Á±…¹”€˜]•‰M½­•Ğ¡Õˆ+ŠB·BP€vÖ–âç®).İ	J›İ]\œËÂ¸¤ »t %( agents.py         # REST controllers for agent lifecycle
â‚íĞ€” €a‘…œ¹Áä€€€€€€€€€€€€Œ¹½‘”ÅÕ•Éä€˜ÑÉ…Ù•ÉÍ…°+ŠB·BP€vÆV6W2ç’2f–ÆRÆö6²7V—6—F–öâb7FGW0®)H"İ	BÆ–&6²ç’2&ö×BÖ–æFW†VBÆ–&6²b&öÆÆ&6°®)H.(	N)HV’ò2æW‡Bæ§2Bf—7VÂfÆ–v‡B&V6÷&FW ®).İ	BØ\Â¸¤ »t %( page.tsx          # Main debugger dashboard
â‚íĞ€” ½µÁ½¹•¹ÑÌ¼+ŠR·BSŠQ‘…œ¼€€€€€€€€€€€€€€ŒI•…Ğ±½Ü…ÕÍ…°É…Á Ù¥ÍÕ…±¥é•È+ŠB·BR‚‡æVÇ2ò2&Æ6¶&ö&BÂÖWG&–72ÂÆ–&6²&"ÂæB–ç7V7F÷ ®)H.(	N(	B67&—G2ğ®).İ	JÙYYÙ[[ËœHÈØÜš\ÈÙYY[™[ˆ][KXYÙ[˜Z[\™H[[Â¸¥ ¸ %9)$È\İËÂ¸¤ »t %test_dag.py          # DAG traversal and invalidation tests
â”œâ”€README.md
```

---

## ğŸ™© Quick Start

### Prerequisites
* **Python 3.11+**
* **Node.js 18+** and **pnpm**
* **Git 2.30+
**
* **Ollama** (optional, for local SLM routing): `ollama pull qwen2.5-coder:7b`

### 1. Clone the Repository
```bash
git clone https://github.com/codebreaker77/CAUSA.git
cd CAUSA
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
\[œİ[\ˆ™\]Z\™[Y[Ë˜‚ŒÈÈÈËˆœ›Û[™Ù]\™Ø˜\Ú˜Ù\ËİZBœœH[œİ[˜‚ˆÈÈÈˆ[ˆØ]\ØHØØ[B˜˜\ÚˆÈ\›Z[˜[Nˆİ\Ø]\ØHÛÛ›Û[™HTB]šXÛÜ›ˆ\Ë˜\K›XZ[˜\KZÜİŒŒŒK\ÜK\™[ØY‚ˆÈ\›Z[˜[ˆİ\Ø]\ØHš\İX[XYÙÙ\ˆRB˜Ù\ËİZBœœH]‚˜“Ü[ˆ
Š–Ú‹ËÛØØ[ÜİŒÌJ‹ËÛØØ[ÜİŒÌ
JŠˆ[ˆ[İ\ˆœ›İÜÙ\‹‚‚‹KKB‚ˆÈÈ8¦¤’İÈØ]\ØHÛÛ\\™\Â‚Ÿ™X]\™H˜]ÈYÙ[\›™\ÜÙ\È
ZY\‹XÛÙKÕÑKX™[˜Ú
H][KPYÙ[œ˜[Y]ÛÜšÜÈ
]]ÑÙ[‹Ü™]ĞRJH
ŠØ]\ØJŠˆŸ‹KK_‹KK_‹KK_‹KK_Ÿ
Š‘^Xİ][Ûˆ\˜YYÛJŠˆ[™X\ˆ\[™[Û›H˜[œØÜš\\›‹X˜\ÙYÛÛ™\œØ][Û˜[Ú]
Š“›Û›[™X\ˆØ]\Ø[QÊŠŸŸ
ŠÛÛ˜İ\œ™[˜ŞHØY™]JŠˆ›Û™H
ÛÛ\Ú[ÛœÈZÙ[JHÛÙ›Û\ÛÛÜ™[˜][Ûˆ
Š‘]\›Z[š\İXÈ™KPÛÛ[Z]X\Ù\ÊŠˆŸ
Š‘š[\Ş\İ[H\ÛÛ][ÛŠŠˆÚ\™YÚ[™ÛH›Û\ˆÚ\™YÜˆÛÛZ[™\‹X˜\ÙY
Š”\‹XYÙ[Ú]ÛÜšİ™Y\ÊŠˆŸ
Š’[\™˜XÙH]Ø\™[™\ÜÊŠˆ[š[H[š™Xİ[Ûˆ
ÚÙ[ˆX]JH˜]Èİš[™È\ÜÚ[™È
ŠTÕÚÙ[]ÛœÈ	ˆ›XÚØ›Ø\™
ŠˆŸ
Š‘˜Z[\™H™XÛİ™\JŠˆ™]HÛÜ
ÛÛ\İ[™[™È\œ›ÜœÊH™\İ\Ù\ÜÚ[Ûˆ
ŠÛİ[\™˜XİX[[YKU˜]™[™]Ú[™
ŠˆŸ
Š‘\œ›ÜˆXYÛ›ÜİXÜÊŠˆX[X[\›Z[˜[ÙÈ[œÜXİ[Ûˆ˜[œØÜš\ØÜ›Û[™È
Š‘š\œİP˜YQXÚ\Ú[ÛˆØØ[^˜][ÛŠŠˆŸ
ŠÜ›ÜÜËPYÙ[›YY
Šˆ[™]XİYØ\ØØY[™È\œ›ÜœÈÚ[[›Û\Û][Ûˆ
Š•˜[œÚ]]™HØ]\Ø[[˜[Y][ÛŠŠˆ‚‹KKB‚ˆÈÈ<'äçXÙ[œÙB‚•\È›Ú™Xİ\ÈXÙ[œÙY[™\ˆHRUXÙ[œÙH8 % see the [LICENSE](LICENSE) file for details.


## ğŸ’‘ Authors & Contributors

* **Vismay Shrouty** ([@codebreaker77]https://github.com/codebreaker77) - *Architecture & System Design*
