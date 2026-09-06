import React, { useMemo, useState, useCallback } from "react";
import {
  Activity, AlertTriangle, ArrowRight, Check, ChevronDown,
  ChevronRight, Code2, Copy, Cpu, Database, Eye, FileCode2,
  GitBranch, GitFork, HelpCircle, Layers, Maximize2, Minimize2,
  MoreHorizontal, Pause, Play, RotateCcw, Search, Settings2,
  Shield, ShieldAlert, SkipBack, SkipForward, Sliders, Sparkles,
  Terminal, Trash2, X, Zap, Magnet, PlusCircle, Edit3, Send
} from "lucide-react";
import {
  Background, Controls, MiniMap, ReactFlow, Handle, Position,
  MarkerType, useEdgesState, useNodesState
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

// Earth Tone Socket Colors (categorized by Causa data type)
const SOCKET_COLORS = {
  prompt: "#d4a359",     // Ochre Gold Sand (Prompt directive)
  ast: "#7a9a60",        // Muted Sage Green (AST interface / Code geometry)
  mutation: "#b86b53",   // Terracotta Clay (Filesystem state / Relational mutation)
  tool: "#8c7a6b",       // Taupe Slate (Tool stream / Execution I/O)
  status: "#b5a895",     // Sandstone / Linen Grey (Exit code / Lease state)
  error: "#b84a39"       // Burnt Sienna / Rust Red (Failure / Exception)
};

// Earth Tone Header Colors (categorized by Causa action type)
const HEADER_COLORS = {
  prompt: "#a67c37",      // Raw Ochre (Prompt Task)
  reasoning: "#8a5a44",   // Warm Terracotta Chestnut (Chain of Thought / Plan)
  tool: "#4e4842",        // Taupe Charcoal (CLI / MCP Tool)
  mutation: "#8b3a2b",    // Burnt Umber / Brick Earth (Filesystem Mutation)
  ast: "#4e6e44",         // Forest Sage Moss (Blackboard AST Contract)
  error: "#7a2319"        // Deep Crimson Rust (Failure / First-Bad-Decision)
};

// Per-Model Tokens Data (Earth tones)
const MODEL_TOKENS = [
  { model: "Claude 3.5 Sonnet", agent: "Orchestrator", tokens: 42150, percent: 21.4, color: "#d4a359", cost: "$0.63" },
  { model: "GPT-4o", agent: "Auth-Worker", tokens: 84620, percent: 43.0, color: "#7a9a60", cost: "$0.42" },
  { model: "Gemini 1.5 Pro", agent: "DB-Migration", tokens: 57430, percent: 29.2, color: "#b86b53", cost: "$0.20" },
  { model: "Llama 3 8B (Local SLM)", agent: "Housekeeping", tokens: 12800, percent: 6.5, color: "#d97736", cost: "$0.00 (Local)" }
];

// Swarm Agent Definitions
const AGENTS = [
  { id: "a1", name: "Orchestrator", short: "orch", color: "#d4a359", model: "Claude 3.5 Sonnet" },
  { id: "a2", name: "Auth-Worker", short: "auth", color: "#7a9a60", model: "GPT-4o" },
  { id: "a3", name: "DB-Migration", short: "db", color: "#b86b53", model: "Gemini 1.5 Pro" }
];

// Real Causa Causal DAG Steps (Styled with Blender Node Structure)
const INITIAL_CAUSA_STEPS = [
  {
    id: "s1",
    promptNum: 1,
    agent: "a1",
    type: "prompt",
    title: "Task Decomposition",
    headerColor: HEADER_COLORS.prompt,
    model: "Claude 3.5 Sonnet",
    agentName: "Orchestrator",
    slmRationale: "SLM Router: High-level architectural decomposition & multi-agent task planning. Dispatched to Claude 3.5 Sonnet for superior dependency planning and minimal drift across sub-tasks.",
    promptText: "Analyze Prisma schema migration impact on authentication middleware and partition into isolated worktree tasks.",
    selectOptions: ["Partition: Worktree Sandboxed", "Strategy: Non-Blocking"],
    inputs: [
      { id: "in_goal", label: "Objective", color: SOCKET_COLORS.prompt, shape: "diamond" }
    ],
    outputs: [
      { id: "out_plan", label: "Plan Directive", color: SOCKET_COLORS.prompt, shape: "diamond" },
      { id: "out_const", label: "Path Constraints", color: SOCKET_COLORS.status, shape: "circle" }
    ],
    tokens: { system: 15, files: 35, tools: 20, history: 30, count: 6200 },
    diff: null,
    x: 40,
    y: 70
  },
  {
    id: "s2",
    promptNum: 1,
    agent: "a1",
    type: "reasoning",
    title: "Select Migration Strategy",
    headerColor: HEADER_COLORS.reasoning,
    model: "Claude 3.5 Sonnet",
    agentName: "Orchestrator",
    slmRationale: "SLM Router: Chain-of-thought constraint solver. Claude 3.5 Sonnet evaluated 3 migration paths; selected lease-guarded non-blocking index approach.",
    promptText: "Evaluate trade-off between cascade deletion vs backward-compatible session index. Output contract specifications.",
    selectOptions: ["Strategy: Backward-Compatible Index"],
    hasPrecommitLock: true,
    inputs: [
      { id: "in_plan", label: "Plan Directive", color: SOCKET_COLORS.prompt, shape: "diamond" },
      { id: "in_cost", label: "Cost Bound", color: SOCKET_COLORS.status, val: "0.500", shape: "circle" }
    ],
    outputs: [
      { id: "out_auth_spec", label: "Auth Contract Spec", color: SOCKET_COLORS.ast, shape: "circle" },
      { id: "out_db_spec", label: "DB Schema Spec", color: SOCKET_COLORS.mutation, shape: "diamond" }
    ],
    tokens: { system: 15, files: 40, tools: 20, history: 25, count: 7400 },
    diff: null,
    x: 290,
    y: 70
  },
  {
    id: "s3",
    promptNum: 2,
    agent: "a2",
    type: "tool",
    title: "Inspect Auth Middleware",
    headerColor: HEADER_COLORS.tool,
    model: "GPT-4o",
    agentName: "Auth-Worker",
    slmRationale: "SLM Router: Fast AST tokenization and strict TypeScript middleware type validation. Dispatched to GPT-4o for rapid code-symbol inspection.",
    promptText: "Check src/middleware/auth.ts to confirm active session token serialization contracts.",
    dropdowns: ["Target: src/middleware/auth.ts", "AST Parser: TypeScript 5.4"],
    inputs: [
      { id: "in_auth_spec", label: "Auth Contract Spec", color: SOCKET_COLORS.ast, shape: "circle" },
      { id: "in_timeout", label: "Timeout (s)", color: SOCKET_COLORS.status, val: "30.00", shape: "circle" }
    ],
    outputs: [
      { id: "out_tok", label: "Session Token Schema", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 10, files: 55, tools: 20, history: 15, count: 9100 },
    diff: null,
    x: 540,
    y: 230
  },
  {
    id: "s4",
    promptNum: 2,
    agent: "a2",
    type: "ast",
    title: "Read AST Session Contract",
    headerColor: HEADER_COLORS.ast,
    model: "GPT-4o",
    agentName: "Auth-Worker",
    slmRationale: "SLM Router: Query SQLite blackboard for interface contract v2.0 published by db-migration worktree.",
    promptText: "SELECT * FROM interface_contracts WHERE name = 'session.contract';",
    inputs: [
      { id: "in_tok", label: "Session Token Schema", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    outputs: [
      { id: "out_diff", label: "Interface Contract v2.0", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 10, files: 60, tools: 15, history: 15, count: 8200 },
    diff: null,
    x: 790,
    y: 230
  },
  {
    id: "s5",
    promptNum: 3,
    agent: "a3",
    type: "tool",
    title: "Read Prisma Schema",
    headerColor: HEADER_COLORS.tool,
    model: "Gemini 1.5 Pro",
    agentName: "DB-Migration",
    slmRationale: "SLM Router: Deep database schema verification. Dispatched to Gemini 1.5 Pro to reason across large database schema with foreign key constraints.",
    promptText: "Read prisma/schema.prisma and inspect Session relation to User model.",
    dropdowns: ["File: prisma/schema.prisma", "Engine: PostgreSQL 16"],
    inputs: [
      { id: "in_db_spec", label: "DB Schema Spec", color: SOCKET_COLORS.mutation, shape: "diamond" }
    ],
    outputs: [
      { id: "out_vertices", label: "Model Session Vertices", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 15, files: 50, tools: 20, history: 15, count: 11400 },
    diff: null,
    x: 540,
    y: 390
  },
  {
    id: "s6",
    promptNum: 3,
    agent: "a3",
    type: "mutation",
    title: "Update schema.prisma",
    headerColor: HEADER_COLORS.mutation,
    model: "Gemini 1.5 Pro",
    agentName: "DB-Migration",
    slmRationale: "SLM Router: Relational schema file mutation with Ferry pre-commit locking. Gemini 1.5 Pro modified index and cascade constraint.",
    promptText: "Add @@index([userId]) to Session model in prisma/schema.prisma.",
    diff: `--- a/prisma/schema.prisma\n+++ b/prisma/schema.prisma\n@@ -18,4 +18,6 @@ model Session {\n   expiresAt DateTime\n   userId    String\n+  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)\n+  @@index([userId])\n }`,
    inputs: [
      { id: "in_vertices", label: "Model Session Vertices", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    outputs: [
      { id: "out_mut_diff", label: "Worktree Diff", color: SOCKET_COLORS.mutation, shape: "diamond" },
      { id: "out_lease", label: "Pre-Commit Lease", color: SOCKET_COLORS.status, shape: "circle" }
    ],
    tokens: { system: 15, files: 45, tools: 20, history: 20, count: 12800 },
    x: 790,
    y: 390
  },
  {
    id: "s7",
    promptNum: 4,
    agent: "a1",
    type: "reasoning",
    title: "Reconcile Contract Mismatch",
    headerColor: HEADER_COLORS.reasoning,
    model: "Claude 3.5 Sonnet",
    agentName: "Orchestrator",
    slmRationale: "SLM Router: Inter-agent contract reconciliation. Claude 3.5 Sonnet detected diff between Auth adapter expectation and Prisma index.",
    promptText: "Reconcile Auth-Worker session contract v2 with modified DB-Migration cascade rule.",
    inputs: [
      { id: "in_iface", label: "Interface Contract v2.0", color: SOCKET_COLORS.ast, shape: "circle" },
      { id: "in_diff", label: "Worktree Diff", color: SOCKET_COLORS.mutation, shape: "diamond" }
    ],
    outputs: [
      { id: "out_patch_spec", label: "Adapter Patch Spec", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 20, files: 35, tools: 20, history: 25, count: 8900 },
    diff: null,
    x: 1030,
    y: 70
  },
  {
    id: "s8",
    promptNum: 4,
    agent: "a2",
    type: "mutation",
    title: "Patch Auth Adapter",
    headerColor: HEADER_COLORS.ast,
    model: "GPT-4o",
    agentName: "Auth-Worker",
    slmRationale: "SLM Router: Targeted adapter patch. GPT-4o updated session validation adapter to match new schema indices.",
    promptText: "Update src/auth/adapter.ts to accommodate cascade deletion of expired session tokens.",
    diff: `--- a/src/auth/adapter.ts\n+++ b/src/auth/adapter.ts\n@@ -42,3 +42,4 @@ export async function getSession(id) {\n-  return db.session.findUnique({ where: { id } });\n+  return db.session.findFirst({ where: { id, expiresAt: { gt: new Date() } } });\n }`,
    inputs: [
      { id: "in_patch_spec", label: "Adapter Patch Spec", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    outputs: [
      { id: "out_patched", label: "Patched Worktree", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 10, files: 50, tools: 20, history: 20, count: 9600 },
    x: 1250,
    y: 230
  },
  {
    id: "s9",
    promptNum: 5,
    agent: "a3",
    type: "error",
    title: "Dry-Run Migration Failed (FBD)",
    headerColor: HEADER_COLORS.error,
    model: "Gemini 1.5 Pro",
    agentName: "DB-Migration",
    isFbd: true,
    slmRationale: "SLM Diagnostic: Ferry pre-commit rejected write! Foreign Key constraint failed during isolated worktree SQLite dry-run test.",
    promptText: "npx prisma migrate dev --dry-run returned exit status 1. Schema contains cyclic dependency.",
    inputs: [
      { id: "in_lease", label: "Pre-Commit Lease", color: SOCKET_COLORS.status, shape: "circle" }
    ],
    outputs: [
      { id: "out_err", label: "Exit Code 1 (FK Cycle)", color: SOCKET_COLORS.error, shape: "circle" }
    ],
    tokens: { system: 10, files: 40, tools: 25, history: 25, count: 8400 },
    diff: null,
    x: 1030,
    y: 390
  },
  {
    id: "s10",
    promptNum: 6,
    agent: "a1",
    type: "prompt",
    title: "Retry: Compatibility Guard",
    headerColor: HEADER_COLORS.prompt,
    model: "Claude 3.5 Sonnet",
    agentName: "Orchestrator",
    slmRationale: "SLM Router: Error recovery dispatch. Claude 3.5 Sonnet formulated counter-strategy to bypass cyclic dependency using non-destructive index.",
    promptText: "Regenerate migration script with compatibility flag to avoid cyclic constraint on Session.",
    inputs: [
      { id: "in_err", label: "Exit Code 1 (FK Cycle)", color: SOCKET_COLORS.error, shape: "circle" }
    ],
    outputs: [
      { id: "out_guard_spec", label: "Non-Destructive Directive", color: SOCKET_COLORS.prompt, shape: "diamond" }
    ],
    tokens: { system: 20, files: 40, tools: 20, history: 20, count: 9800 },
    diff: null,
    x: 1470,
    y: 70
  },
  {
    id: "s11",
    promptNum: 6,
    agent: "a3",
    type: "mutation",
    title: "Apply Compatibility Index",
    headerColor: HEADER_COLORS.mutation,
    model: "Gemini 1.5 Pro",
    agentName: "DB-Migration",
    slmRationale: "SLM Router: Re-execution with corrected parameters. Gemini 1.5 Pro generated non-blocking index.",
    promptText: "Apply CREATE INDEX CONCURRENTLY on Session(userId).",
    diff: `--- a/prisma/schema.prisma\n+++ b/prisma/schema.prisma\n@@ -21,1 +21,1 @@\n-  @@index([userId])\n+  @@index([userId], map: "idx_session_user_compat")`,
    inputs: [
      { id: "in_guard_spec", label: "Non-Destructive Directive", color: SOCKET_COLORS.prompt, shape: "diamond" }
    ],
    outputs: [
      { id: "out_compat_diff", label: "Compatible Schema Diff", color: SOCKET_COLORS.mutation, shape: "diamond" }
    ],
    tokens: { system: 15, files: 45, tools: 20, history: 20, count: 10200 },
    x: 1250,
    y: 390
  },
  {
    id: "s12",
    promptNum: 7,
    agent: "a2",
    type: "tool",
    title: "Run Integration Tests",
    headerColor: HEADER_COLORS.tool,
    model: "GPT-4o",
    agentName: "Auth-Worker",
    slmRationale: "SLM Router: Test suite execution. GPT-4o executed Jest suite in isolated worktree.",
    promptText: "npm test -- tests/auth-session.test.ts",
    inputs: [
      { id: "in_patched", label: "Patched Worktree", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    outputs: [
      { id: "out_passed", label: "Jest Test Passed (100%)", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 10, files: 50, tools: 30, history: 10, count: 7900 },
    diff: null,
    x: 1470,
    y: 230
  },
  {
    id: "s13",
    promptNum: 7,
    agent: "a3",
    type: "ast",
    title: "Verify & Release Swarm Leases",
    headerColor: HEADER_COLORS.ast,
    model: "Gemini 1.5 Pro",
    agentName: "DB-Migration",
    slmRationale: "SLM Router: Final blackboard verification and lease release. Gemini 1.5 Pro broadcasted verified AST contract.",
    promptText: "Commit AST interface contract v2.1 to SQLite blackboard and release db/write lock.",
    inputs: [
      { id: "in_compat_diff", label: "Compatible Schema Diff", color: SOCKET_COLORS.mutation, shape: "diamond" },
      { id: "in_passed", label: "Jest Test Passed (100%)", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    outputs: [
      { id: "out_verified", label: "Verified AST v2.1", color: SOCKET_COLORS.ast, shape: "circle" }
    ],
    tokens: { system: 10, files: 60, tools: 15, history: 15, count: 6800 },
    diff: null,
    x: 1690,
    y: 390
  }
];

// Causa Causal Wires connecting the steps
const INITIAL_CAUSA_EDGES = [
  { id: "e1", source: "s1", target: "s2", color: SOCKET_COLORS.prompt, subAgent: "Orchestrator", jobTitle: "Solve Migration Constraints", jobReason: "Determine minimal blast radius plan before spawning workers", payload: "Task breakdown + dependency constraints" },
  { id: "e2", source: "s2", target: "s3", color: SOCKET_COLORS.ast, subAgent: "Auth-Worker", jobTitle: "Inspect Auth Middleware", jobReason: "Verify whether active middleware reads session.userId directly or via token cache", payload: "Scoped path: src/middleware/auth.ts" },
  { id: "e3", source: "s2", target: "s5", color: SOCKET_COLORS.mutation, subAgent: "DB-Migration", jobTitle: "Verify Prisma Relations", jobReason: "Check foreign key cascade behavior in existing schema.prisma", payload: "Target file: prisma/schema.prisma" },
  { id: "e4", source: "s3", target: "s4", color: SOCKET_COLORS.ast, subAgent: "Auth-Worker", jobTitle: "Read Blackboard Contract", jobReason: "Ensure auth middleware matches published AST interface contract v2.0", payload: "Contract query: session.contract" },
  { id: "e5", source: "s5", target: "s6", color: SOCKET_COLORS.ast, subAgent: "DB-Migration", jobTitle: "Apply Schema Mutation", jobReason: "Inject foreign key index and cascade deletion rule into schema", payload: "Mutation AST diff (@@index + onDelete)" },
  { id: "e6", source: "s4", target: "s7", color: SOCKET_COLORS.ast, subAgent: "Orchestrator", jobTitle: "Sync Contract Diff", jobReason: "Detect discrepancies between Auth adapter expectation and DB schema", payload: "AST Interface mismatch report" },
  { id: "e7", source: "s6", target: "s7", color: SOCKET_COLORS.mutation, subAgent: "Orchestrator", jobTitle: "Review Pre-Commit Hook", jobReason: "Ferry intercepted schema mutation pending compatibility verification", payload: "Uncommitted worktree diff" },
  { id: "e8", source: "s7", target: "s8", color: SOCKET_COLORS.ast, subAgent: "Auth-Worker", jobTitle: "Patch Auth Adapter", jobReason: "Align auth adapter lookup with newly indexed session table", payload: "Modified query contract" },
  { id: "e9", source: "s6", target: "s9", color: SOCKET_COLORS.status, subAgent: "DB-Migration", jobTitle: "Execute Dry-Run Migration", jobReason: "Test schema change inside isolated Git worktree before committing", payload: "npx prisma migrate dev --dry-run" },
  { id: "e10", source: "s9", target: "s10", color: SOCKET_COLORS.error, subAgent: "Orchestrator", jobTitle: "Handle Migration Failure (FBD)", jobReason: "Transitive invalidation triggered! Formulate counter-strategy", payload: "Exit code 1 + FK cycle error log" },
  { id: "e11", source: "s10", target: "s11", color: SOCKET_COLORS.prompt, subAgent: "DB-Migration", jobTitle: "Apply Compatibility Index", jobReason: "Implement non-blocking compatible index to resolve cycle", payload: "idx_session_user_compat directive" },
  { id: "e12", source: "s8", target: "s12", color: SOCKET_COLORS.ast, subAgent: "Auth-Worker", jobTitle: "Run Integration Suite", jobReason: "Verify patched auth adapter against test suite", payload: "tests/auth-session.test.ts" },
  { id: "e13", source: "s11", target: "s13", color: SOCKET_COLORS.mutation, subAgent: "DB-Migration", jobTitle: "Publish Verified Contract", jobReason: "Broadcast completed migration contract to SQLite blackboard", payload: "AST contract v2.1 + release write lease" },
  { id: "e14", source: "s12", target: "s13", color: SOCKET_COLORS.ast, subAgent: "DB-Migration", jobTitle: "Release Swarm Locks", jobReason: "All worker validations succeeded; signal swarm completion", payload: "Integration test pass receipt" }
];

// Blender-Styled Causa Node Card
function BlenderCausaNode({ data }) {
  const isSelected = data.isSelected;
  const isFbd = data.isFbd;
  const isReverted = data.isReverted;
  const isGhost = data.isGhost;

  return (
    <div
      className={`blender-node min-w-[205px] relative select-none cursor-grab active:cursor-grabbing
        ${isGhost ? "dashed-preview" : ""}
        ${isSelected ? "selected" : ""}
        ${isFbd ? "blender-fbd" : ""}
        ${isReverted ? "opacity-35 line-through border-rose-900 bg-[#251b1c]" : ""}`}
    >
      {/* Node Header Bar */}
      <div
        className="flex items-center justify-between px-2.5 py-1 rounded-t-[5px] text-[11px] font-medium text-white shadow-inner cursor-grab active:cursor-grabbing"
        style={{ backgroundColor: data.headerColor }}
      >
        <div className="flex items-center gap-1.5 pointer-events-none">
          <span className="text-[9px] opacity-80">▾</span>
          <span className="tracking-tight">{data.title}</span>
        </div>
        <div className="flex items-center gap-1 pointer-events-none">
          <span className="text-[8px] opacity-75 font-mono">P#{data.promptNum}</span>
          {isGhost && (
            <span className="bg-[#e67e22] text-black text-[8px] px-1 rounded font-bold uppercase">
              Preview
            </span>
          )}
          {isFbd && <span className="bg-rose-900/80 text-rose-200 text-[8px] px-1 rounded font-bold">FBD</span>}
        </div>
      </div>

      {/* Node Body */}
      <div className="p-2 space-y-1.5 text-[10px] text-[#cfcfcf]">
        {/* Model dropdown / option selector */}
        <div className="flex items-center justify-between border-b border-[#2a2a2a] pb-1 mb-1">
          <span className="text-[9px] font-mono text-[#888]">{data.agentName}</span>
          <span className="text-[9px] font-mono text-[#e5b82c] bg-[#222] px-1.5 py-0.5 rounded border border-[#1a1a1a]">
            {data.model.split(" ")[0]}
          </span>
        </div>

        {data.selectOptions && (
          <div className="mb-1">
            <select className="blender-select w-full nodrag" defaultValue={data.selectOptions[0]}>
              {data.selectOptions.map((opt, i) => <option key={i}>{opt}</option>)}
            </select>
          </div>
        )}

        {data.dropdowns && (
          <div className="space-y-1 mb-1">
            {data.dropdowns.map((d, i) => (
              <select key={i} className="blender-select w-full nodrag" defaultValue={d}>
                <option>{d}</option>
              </select>
            ))}
          </div>
        )}

        {/* Inputs (Left) and Outputs (Right) */}
        <div className="space-y-1.5 pt-0.5">
          {/* Inputs */}
          {data.inputs.map((inp, idx) => (
            <div key={idx} className="relative flex items-center justify-between min-h-[18px]">
              <Handle
                type="target"
                position={Position.Left}
                id={inp.id}
                className={`blender-socket ${inp.shape === "diamond" ? "blender-socket-diamond" : "blender-socket-circle"}`}
                style={{ backgroundColor: inp.color, left: -5 }}
              />
              <span className="pl-2 text-[10px] text-[#b0b0b0]">{inp.label}</span>
              {inp.val && (
                <input
                  type="text"
                  defaultValue={inp.val}
                  className="blender-input w-14 nodrag"
                  onClick={(e) => e.stopPropagation()}
                />
              )}
            </div>
          ))}

          {/* Outputs */}
          {data.outputs.map((out, idx) => (
            <div key={idx} className="relative flex items-center justify-end min-h-[18px]">
              <span className="pr-2 text-[10px] text-[#cfcfcf]">{out.label}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={out.id}
                className={`blender-socket ${out.shape === "diamond" ? "blender-socket-diamond" : "blender-socket-circle"}`}
                style={{ backgroundColor: out.color, right: -5 }}
              />
            </div>
          ))}
        </div>

        {/* Action Controls on Node (Fork & Revert/Delete) */}
        {!isGhost && (
          <div className="border-t border-[#292929] pt-1.5 mt-2 flex items-center justify-end gap-1.5">
            <button
              title="Fork Counterfactual Branch"
              onClick={(e) => {
                e.stopPropagation();
                data.onFork(data);
              }}
              className="nodrag flex items-center gap-1 rounded bg-[#252525] hover:bg-[#303030] px-2 py-0.5 text-[9px] text-[#e5b82c] border border-[#333]"
            >
              <GitFork size={9} /> Fork
            </button>
            <button
              title="Delete & Revert Prompt"
              onClick={(e) => {
                e.stopPropagation();
                data.onRevert(data);
              }}
              className="nodrag flex items-center gap-1 rounded bg-[#252525] hover:bg-[#3a2020] px-2 py-0.5 text-[9px] text-[#eb4d4b] border border-[#333]"
            >
              <Trash2 size={9} /> Revert
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { blenderCausaNode: BlenderCausaNode };

const INITIAL_WORKFLOWS = [
  {
    id: "wf_oauth",
    title: "OAuth2 & Session Refactor",
    totalPrompts: 7,
    activePrompt: 3,
    stepsData: INITIAL_CAUSA_STEPS,
    userPromptInput: "Add Redis caching layer to src/auth/adapter.ts with 3600s TTL for valid session tokens to reduce postgres connection pool pressure.",
    isPlanPending: false,
    proposedSubtasks: [
      {
        id: "sub_1",
        agentId: "a1",
        agentName: "Orchestrator",
        model: "Claude 3.5 Sonnet",
        role: "Architectural Cache Strategy",
        prompt: "Design Redis session token cache invalidation rules and error fallback policies.",
        nodeTitle: "Plan Redis Cache Strategy"
      },
      {
        id: "sub_2",
        agentId: "a2",
        agentName: "Auth-Worker",
        model: "GPT-4o",
        role: "Redis Adapter Implementation",
        prompt: "Inject redis.get / redis.set with 3600s TTL into src/auth/adapter.ts without breaking getSession signature.",
        nodeTitle: "Implement Redis Adapter Cache"
      },
      {
        id: "sub_3",
        agentId: "a3",
        agentName: "DB-Migration",
        model: "Gemini 1.5 Pro",
        role: "Blackboard Cache Contract Sync",
        prompt: "Broadcast session.cache.contract v1.0 to SQLite blackboard and register cache read lease.",
        nodeTitle: "Sync Cache Contract Blackboard"
      }
    ],
    revertedIds: new Set(),
    selectedNode: INITIAL_CAUSA_STEPS[5],
    edgesData: INITIAL_CAUSA_EDGES
  },
  {
    id: "wf_stripe",
    title: "Stripe Webhook Verification",
    totalPrompts: 2,
    activePrompt: 2,
    stepsData: [
      {
        id: "sw_1",
        promptNum: 1,
        agent: "a1",
        type: "prompt",
        title: "Stripe Webhook Directive",
        headerColor: HEADER_COLORS.prompt,
        model: "Claude 3.5 Sonnet",
        agentName: "Orchestrator",
        slmRationale: "SLM Router: Cryptographic webhook signature verification and idempotent processing contract.",
        promptText: "Implement stripe-signature header validation using raw request body buffer in API route handler.",
        inputs: [{ id: "in_stripe", label: "Webhook Event", color: SOCKET_COLORS.prompt, shape: "diamond" }],
        outputs: [{ id: "out_verified", label: "Verified Event Spec", color: SOCKET_COLORS.ast, shape: "circle" }],
        tokens: { system: 15, files: 30, tools: 20, history: 15, count: 4800 },
        diff: null,
        x: 60,
        y: 120
      },
      {
        id: "sw_2",
        promptNum: 2,
        agent: "a2",
        type: "mutation",
        title: "Verify Webhook Signature",
        headerColor: HEADER_COLORS.mutation,
        model: "GPT-4o",
        agentName: "Auth-Worker",
        slmRationale: "SLM Router: HMAC SHA-256 signature verification in src/api/webhooks/stripe.ts.",
        promptText: "Construct stripe.webhooks.constructEvent(buf, sig, endpointSecret) with timing-safe comparison.",
        diff: `--- a/src/api/webhooks/stripe.ts\n+++ b/src/api/webhooks/stripe.ts\n@@ -12,2 +12,5 @@\n+ const event = stripe.webhooks.constructEvent(req.rawBody, sig, secret);\n+ await handleIdempotentEvent(event.id);`,
        inputs: [{ id: "in_sig", label: "Signature Header", color: SOCKET_COLORS.ast, shape: "circle" }],
        outputs: [{ id: "out_ack", label: "200 ACK", color: SOCKET_COLORS.status, shape: "circle" }],
        tokens: { system: 10, files: 40, tools: 15, history: 10, count: 6200 },
        x: 340,
        y: 120
      }
    ],
    edgesData: [
      { id: "se_1", source: "sw_1", target: "sw_2", color: SOCKET_COLORS.ast, subAgent: "Auth-Worker", jobTitle: "Verify Webhook Signature", jobReason: "Direct HMAC implementation", payload: "ConstructEvent payload" }
    ],
    userPromptInput: "Fix Stripe webhook signature validation bypass error and add idempotency check",
    isPlanPending: false,
    proposedSubtasks: [],
    revertedIds: new Set(),
    selectedNode: null
  }
];

const createInitialNodes = (steps = INITIAL_CAUSA_STEPS) => {
  return steps.map((s) => ({
    id: s.id,
    type: "blenderCausaNode",
    position: { x: s.x, y: s.y },
    data: {
      ...s,
      isSelected: s.id === "s6",
      isReverted: false,
      isGhost: false
    }
  }));
};

export default function App() {
  // === WORKFLOW TAB MANAGEMENT STATE ===
  const [workflows, setWorkflows] = useState(INITIAL_WORKFLOWS);
  const [activeWorkflowId, setActiveWorkflowId] = useState("wf_oauth");

  const [isNewWorkflowModalOpen, setIsNewWorkflowModalOpen] = useState(false);
  const [newWfTitleInput, setNewWfTitleInput] = useState("");
  const [newWfTemplateType, setNewWfTemplateType] = useState("blank");

  // Get active workflow object
  const activeWorkflow = useMemo(() => {
    return workflows.find((w) => w.id === activeWorkflowId) || workflows[0];
  }, [workflows, activeWorkflowId]);

  // Derived current tab state properties:
  const stepsData = activeWorkflow.stepsData;
  const totalPrompts = activeWorkflow.totalPrompts;
  const activePrompt = activeWorkflow.activePrompt;
  const selectedNode = activeWorkflow.selectedNode;
  const isPlanPending = activeWorkflow.isPlanPending;
  const proposedSubtasks = activeWorkflow.proposedSubtasks;
  const userPromptInput = activeWorkflow.userPromptInput;
  const revertedIds = activeWorkflow.revertedIds;
  const edgesData = activeWorkflow.edgesData || INITIAL_CAUSA_EDGES;

  const [paused, setPaused] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true); // Blender N-Panel
  const [sidebarTab, setSidebarTab] = useState("slm"); // 'node' | 'slm' | 'diff' | 'plan'
  const [tokenMenuOpen, setTokenMenuOpen] = useState(false);
  const [blackboardOpen, setBlackboardOpen] = useState(false);
  const [forkModalOpen, setForkModalOpen] = useState(false);
  const [forkPromptInput, setForkPromptInput] = useState("");
  const [toast, setToast] = useState("");

  const [isEnterPromptModalOpen, setIsEnterPromptModalOpen] = useState(false);
  const [isSlmThinking, setIsSlmThinking] = useState(false);
  const [telemetry, setTelemetry] = useState({ contracts: [], leases: [], metrics: {} });

  // Real-time telemetry polling from Causa Control Plane API
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const resp = await fetch("http://localhost:8000/api/telemetry");
        if (resp.ok) {
          const data = await resp.json();
          setTelemetry(data);
        }
      } catch (err) {
        // API offline or booting, maintain default state
      }
    };
    fetchTelemetry();
    const timer = setInterval(fetchTelemetry, 3000);
    return () => clearInterval(timer);
  }, []);

  // Helper to update active workflow state cleanly:
  const updateActiveWorkflowData = useCallback((patch) => {
    setWorkflows((prevWorkflows) =>
      prevWorkflows.map((w) => {
        if (w.id === activeWorkflowId) {
          const updated = typeof patch === "function" ? patch(w) : patch;
          return { ...w, ...updated };
        }
        return w;
      })
    );
  }, [activeWorkflowId]);

  // Delegated state setters:
  const setStepsData = (updater) => {
    updateActiveWorkflowData((w) => ({
      stepsData: typeof updater === "function" ? updater(w.stepsData) : updater
    }));
  };

  const setEdgesData = (updater) => {
    updateActiveWorkflowData((w) => ({
      edgesData: typeof updater === "function" ? updater(w.edgesData || INITIAL_CAUSA_EDGES) : updater
    }));
  };

  const setTotalPrompts = (updater) => {
    updateActiveWorkflowData((w) => ({
      totalPrompts: typeof updater === "function" ? updater(w.totalPrompts) : updater
    }));
  };

  const setActivePrompt = (updater) => {
    updateActiveWorkflowData((w) => ({
      activePrompt: typeof updater === "function" ? updater(w.activePrompt) : updater
    }));
  };

  const setSelectedNode = (updater) => {
    updateActiveWorkflowData((w) => ({
      selectedNode: typeof updater === "function" ? updater(w.selectedNode) : updater
    }));
  };

  const setIsPlanPending = (updater) => {
    updateActiveWorkflowData((w) => ({
      isPlanPending: typeof updater === "function" ? updater(w.isPlanPending) : updater
    }));
  };

  const setProposedSubtasks = (updater) => {
    updateActiveWorkflowData((w) => ({
      proposedSubtasks: typeof updater === "function" ? updater(w.proposedSubtasks) : updater
    }));
  };

  const setUserPromptInput = (updater) => {
    updateActiveWorkflowData((w) => ({
      userPromptInput: typeof updater === "function" ? updater(w.userPromptInput) : updater
    }));
  };

  const setRevertedIds = (updater) => {
    updateActiveWorkflowData((w) => ({
      revertedIds: typeof updater === "function" ? updater(w.revertedIds) : updater
    }));
  };

  // Workflow tab creation & removal
  const handleCreateWorkflow = () => {
    const newId = `wf_${Date.now().toString().slice(-5)}`;
    const title = newWfTitleInput.trim() || `Workflow Session #${workflows.length + 1}`;

    let templateSteps = [];
    let templateEdges = [];
    if (newWfTemplateType === "blank") {
      templateSteps = [
        {
          id: `init_${newId}`,
          promptNum: 1,
          agent: "a1",
          type: "prompt",
          title: "Prompt #1: Initial Directive",
          headerColor: HEADER_COLORS.prompt,
          model: "Claude 3.5 Sonnet",
          agentName: "Orchestrator",
          slmRationale: "Fresh conversation workflow initialized. Enter prompt to decompose with Local SLM.",
          promptText: title,
          inputs: [{ id: "in_init", label: "Objective", color: SOCKET_COLORS.prompt, shape: "diamond" }],
          outputs: [{ id: "out_init", label: "Plan Directive", color: SOCKET_COLORS.prompt, shape: "diamond" }],
          tokens: { system: 10, files: 10, tools: 10, history: 10, count: 1200 },
          diff: null,
          x: 60,
          y: 120
        }
      ];
      templateEdges = [];
    } else if (newWfTemplateType === "stripe") {
      templateSteps = INITIAL_WORKFLOWS[1].stepsData;
      templateEdges = INITIAL_WORKFLOWS[1].edgesData || [];
    } else {
      templateSteps = INITIAL_CAUSA_STEPS;
      templateEdges = INITIAL_CAUSA_EDGES;
    }

    const newWf = {
      id: newId,
      title,
      totalPrompts: templateSteps.length ? Math.max(...templateSteps.map((s) => s.promptNum)) : 1,
      activePrompt: 1,
      stepsData: templateSteps,
      edgesData: templateEdges,
      selectedNode: templateSteps[0] || null,
      isPlanPending: false,
      proposedSubtasks: [],
      userPromptInput: `Objective for ${title}...`,
      revertedIds: new Set()
    };

    setWorkflows((prev) => [...prev, newWf]);
    setActiveWorkflowId(newId);
    setIsNewWorkflowModalOpen(false);
    setNewWfTitleInput("");
    showToast(`Created workflow tab: "${title}"`);
  };

  const handleCloseWorkflowTab = (wfId, event) => {
    event.stopPropagation();
    if (workflows.length <= 1) {
      showToast("Cannot close the last remaining workflow session!");
      return;
    }

    const targetWf = workflows.find((w) => w.id === wfId);
    const nextWorkflows = workflows.filter((w) => w.id !== wfId);
    setWorkflows(nextWorkflows);

    if (activeWorkflowId === wfId) {
      setActiveWorkflowId(nextWorkflows[nextWorkflows.length - 1].id);
    }
    showToast(`Closed workflow tab: "${targetWf?.title || wfId}"`);
  };

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  };

  const handleSelectNode = useCallback((nodeData) => {
    setSelectedNode(nodeData);
    setSelectedEdge(null);
    setActivePrompt(nodeData.promptNum);
  }, []);

  const handleForkNode = useCallback((nodeData) => {
    setSelectedNode(nodeData);
    setForkPromptInput(`Counterfactual from Prompt #${nodeData.promptNum}: `);
    setForkModalOpen(true);
  }, []);

  const handleRevertNode = useCallback((nodeData) => {
    setRevertedIds((prev) => {
      const next = new Set(prev);
      next.add(nodeData.id);
      if (nodeData.id === "s6" || nodeData.id === "s5") {
        next.add("s9");
        next.add("s11");
        next.add("s13");
      }
      return next;
    });
    showToast(`Reverted Prompt #${nodeData.promptNum} (${nodeData.title}). Downstream worktree changes rolled back.`);
  }, []);

  // Submit Prompt to Real SLM for Decomposition
  const handleStartPromptDecomposition = async () => {
    setIsEnterPromptModalOpen(false);
    setIsSlmThinking(true);
    showToast("Astra Local SLM (Ollama) analyzing prompt and architecture...");

    try {
      const resp = await fetch("http://localhost:8000/api/decompose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: userPromptInput }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.proposedSubtasks && data.proposedSubtasks.length > 0) {
          setProposedSubtasks(data.proposedSubtasks);
        }
        showToast(
          data.is_slm_live
            ? `Real Local SLM (${data.slm_model}) assigned tasks! Review dashed preview and click Proceed.`
            : "Astra assigned sub-models! Review dashed preview graph and click Proceed."
        );
      }
    } catch (err) {
      console.warn("Backend API offline, using native preview fallback:", err);
      showToast("Local SLM assigned sub-models! Review dashed preview graph and click Proceed.");
    } finally {
      setIsSlmThinking(false);
      setIsPlanPending(true);
      setSidebarOpen(true);
      setSidebarTab("plan");
    }
  };

  // User clicks "Proceed" in right window: solidifies the preview graph!
  const handleProceedPlan = async () => {
    const nextPromptNum = totalPrompts + 1;
    const promptNodeId = `s_prompt_${nextPromptNum}`;
    const baseNewPromptNode = {
      id: promptNodeId,
      promptNum: nextPromptNum,
      agent: "a1",
      type: "prompt",
      title: `Prompt #${nextPromptNum}: User Objective`,
      headerColor: HEADER_COLORS.prompt,
      model: "Claude 3.5 Sonnet",
      agentName: "Orchestrator",
      slmRationale: `SLM Decomposed user prompt: "${userPromptInput.slice(0, 60)}..." into ${proposedSubtasks.length} sub-agent roles.`,
      promptText: userPromptInput,
      inputs: [{ id: "in_user", label: "User Prompt", color: SOCKET_COLORS.prompt, shape: "diamond" }],
      outputs: [{ id: "out_spec", label: "Cache Spec", color: SOCKET_COLORS.prompt, shape: "diamond" }],
      tokens: { system: 15, files: 35, tools: 20, history: 30, count: 5400 },
      diff: null,
      x: 1890,
      y: 70
    };

    const solidifiedSubnodes = proposedSubtasks.map((st, i) => ({
      id: `s_sub_${nextPromptNum}_${i}`,
      promptNum: nextPromptNum,
      agent: st.agentId || (i === 0 ? "a1" : i === 1 ? "a2" : "a3"),
      type: i === 0 ? "reasoning" : i === 1 ? "mutation" : "ast",
      title: st.nodeTitle,
      headerColor: i === 0 ? HEADER_COLORS.reasoning : i === 1 ? HEADER_COLORS.mutation : HEADER_COLORS.ast,
      model: st.model,
      agentName: st.agentName,
      slmRationale: `Role assigned by SLM: ${st.role}. Dispatched to ${st.model}.`,
      promptText: st.prompt,
      inputs: [{ id: `in_${i}`, label: "Directive", color: SOCKET_COLORS.ast, shape: "circle" }],
      outputs: [{ id: `out_${i}`, label: "Result AST", color: SOCKET_COLORS.mutation, shape: "diamond" }],
      tokens: { system: 15, files: 45, tools: 20, history: 20, count: 7200 },
      diff: null,
      x: 1890 + (i === 0 ? 240 : i === 1 ? 480 : 720),
      y: i === 0 ? 70 : i === 1 ? 230 : 390
    }));

    // Connect causal dependency wires
    const lastNode = stepsData[stepsData.length - 1];
    const newEdges = [
      ...(lastNode ? [{
        id: `e_conn_${lastNode.id}_${promptNodeId}`,
        source: lastNode.id,
        target: promptNodeId,
        color: "#d97736",
        jobTitle: `Feed AST into Prompt #${nextPromptNum}`,
        subAgent: "Orchestrator",
        jobReason: "Sequential causal chain",
        payload: "AST Contract v2.1"
      }] : []),
      ...(solidifiedSubnodes.length > 0 ? [{
        id: `e_conn_${promptNodeId}_${solidifiedSubnodes[0].id}`,
        source: promptNodeId,
        target: solidifiedSubnodes[0].id,
        color: "#d4a359",
        jobTitle: solidifiedSubnodes[0].title,
        subAgent: solidifiedSubnodes[0].agentName,
        jobReason: "Subtask dispatch",
        payload: "Directive"
      }] : [])
    ];

    for (let i = 0; i < solidifiedSubnodes.length - 1; i++) {
      newEdges.push({
        id: `e_conn_${solidifiedSubnodes[i].id}_${solidifiedSubnodes[i + 1].id}`,
        source: solidifiedSubnodes[i].id,
        target: solidifiedSubnodes[i + 1].id,
        color: i === 0 ? "#7a9a60" : "#b86b53",
        jobTitle: solidifiedSubnodes[i + 1].title,
        subAgent: solidifiedSubnodes[i + 1].agentName,
        jobReason: "Pipeline dependency",
        payload: "AST Interface Contract"
      });
    }

    setStepsData((prev) => [...prev, baseNewPromptNode, ...solidifiedSubnodes]);
    setEdgesData((prev) => [...prev, ...newEdges]);
    setTotalPrompts(nextPromptNum);
    setActivePrompt(nextPromptNum);
    setSelectedNode(baseNewPromptNode);
    setIsPlanPending(false);
    setSidebarTab("node");
    showToast(`Swarm plan approved! Prompt #${nextPromptNum} dispatched across worktrees. Executing tasks...`);

    // Call Real Backend API to execute the plan
    try {
      const resp = await fetch("http://localhost:8000/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: userPromptInput,
          subtasks: proposedSubtasks
        })
      });
      if (resp.ok) {
        const execData = await resp.json();
        if (execData.results && execData.results.length > 0) {
          setStepsData((prev) =>
            prev.map((node) => {
              const matchedResult = execData.results.find((r, idx) => `s_sub_${nextPromptNum}_${idx}` === node.id);
              if (matchedResult) {
                return {
                  ...node,
                  diff: matchedResult.diff || node.diff,
                  tokens: {
                    ...node.tokens,
                    count: matchedResult.tokens || node.tokens.count
                  },
                  slmRationale: matchedResult.generatedCode
                    ? `Real Model Output Generated (${matchedResult.tokens} tokens consumed). Contract published to Blackboard.`
                    : node.slmRationale
                };
              }
              return node;
            })
          );
          showToast(`Execution finished! Real SLM generated code & AST contracts across ${execData.results.length} worktrees.`);
        }
      }
    } catch (err) {
      console.warn("Backend execution fallback:", err);
    }
  };

  // User cancels the prospective plan
  const handleDiscardPlan = () => {
    setIsPlanPending(false);
    setSidebarTab("node");
    showToast("Proposed swarm plan discarded.");
  };

  // ReactFlow Edges (combines committed edges + dashed preview edges)
  const flowEdges = useMemo(() => {
    const activeEdges = edgesData || INITIAL_CAUSA_EDGES;
    const baseEdges = activeEdges.map((e) => {
      const isSelected = selectedEdge?.id === e.id;
      const isTainted = revertedIds.has(e.source) || revertedIds.has(e.target);

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: isSelected || e.id === "e9",
        data: e,
        style: {
          stroke: isTainted ? "#b84a39" : e.color,
          strokeWidth: isSelected ? 3.5 : 2.2,
          strokeDasharray: isTainted ? "4 4" : undefined
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isTainted ? "#b84a39" : e.color,
          width: 12,
          height: 12
        }
      };
    });

    if (isPlanPending) {
      const ghostEdges = [
        {
          id: "ghost_e0",
          source: stepsData[stepsData.length - 1]?.id || "s13",
          target: "preview_prompt_root",
          animated: true,
          data: { jobTitle: "Feed AST v2.1 into new Prompt", subAgent: "Orchestrator", jobReason: "Sequential causal chain", payload: "AST Contract v2.1" },
          style: { stroke: "#d97736", strokeWidth: 2.2, strokeDasharray: "5 5" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#d97736", width: 12, height: 12 }
        },
        {
          id: "ghost_e1",
          source: "preview_prompt_root",
          target: "preview_sub_0",
          animated: true,
          data: { jobTitle: "Decompose Directive", subAgent: "Orchestrator", jobReason: "Planning", payload: "Spec" },
          style: { stroke: "#d4a359", strokeWidth: 2.2, strokeDasharray: "5 5" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#d4a359", width: 12, height: 12 }
        },
        {
          id: "ghost_e2",
          source: "preview_sub_0",
          target: "preview_sub_1",
          animated: true,
          data: { jobTitle: "Execute Subtask 1", subAgent: "Auth-Worker", jobReason: "Code mutation", payload: "Setup" },
          style: { stroke: "#7a9a60", strokeWidth: 2.2, strokeDasharray: "5 5" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#7a9a60", width: 12, height: 12 }
        },
        {
          id: "ghost_e3",
          source: "preview_sub_1",
          target: "preview_sub_2",
          animated: true,
          data: { jobTitle: "Sync Contract", subAgent: "DB-Migration", jobReason: "Blackboard update", payload: "Contract" },
          style: { stroke: "#b86b53", strokeWidth: 2.2, strokeDasharray: "5 5" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#b86b53", width: 12, height: 12 }
        }
      ];
      return [...baseEdges, ...ghostEdges];
    }

    return baseEdges;
  }, [edgesData, stepsData, selectedEdge, revertedIds, isPlanPending]);

  const [nodes, setNodes, onNodesChange] = useNodesState(createInitialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  const currentWfIdRef = React.useRef(activeWorkflowId);

  // Synchronize ReactFlow nodes while STRICTLY preserving any user-dragged positions!
  React.useEffect(() => {
    const isTabSwitch = currentWfIdRef.current !== activeWorkflowId;
    currentWfIdRef.current = activeWorkflowId;

    setNodes((prevNodes) => {
      const posMap = new Map();
      if (!isTabSwitch) {
        for (const pn of prevNodes) {
          if (pn.position) {
            posMap.set(pn.id, pn.position);
          }
        }
      }

      const mainNodes = stepsData.map((s) => ({
        id: s.id,
        type: "blenderCausaNode",
        position: posMap.get(s.id) || { x: s.x, y: s.y },
        data: {
          ...s,
          isSelected: selectedNode?.id === s.id,
          isReverted: revertedIds.has(s.id),
          isGhost: false,
          onFork: handleForkNode,
          onRevert: handleRevertNode
        }
      }));

      if (isPlanPending) {
        const nextP = totalPrompts + 1;
        const previewPromptNode = {
          id: "preview_prompt_root",
          type: "blenderCausaNode",
          position: posMap.get("preview_prompt_root") || { x: 1890, y: 70 },
          data: {
            id: "preview_prompt_root",
            promptNum: nextP,
            agentName: "Orchestrator",
            title: `Prompt #${nextP}: User Prompt`,
            headerColor: HEADER_COLORS.prompt,
            model: "Claude 3.5 Sonnet",
            slmRationale: "Prospective prompt node pending user Proceed confirmation.",
            inputs: [{ id: "in_p", label: "Objective", color: SOCKET_COLORS.prompt, shape: "diamond" }],
            outputs: [{ id: "out_p", label: "Plan", color: SOCKET_COLORS.prompt, shape: "diamond" }],
            isGhost: true,
            isSelected: selectedNode?.id === "preview_prompt_root"
          }
        };

        const previewSubNodes = proposedSubtasks.map((st, i) => {
          const subId = `preview_sub_${i}`;
          return {
            id: subId,
            type: "blenderCausaNode",
            position: posMap.get(subId) || { x: 1890 + (i === 0 ? 240 : i === 1 ? 480 : 720), y: i === 0 ? 70 : i === 1 ? 230 : 390 },
            data: {
              id: subId,
              promptNum: nextP,
              agentName: st.agentName,
              title: st.nodeTitle,
              headerColor: i === 0 ? HEADER_COLORS.reasoning : i === 1 ? HEADER_COLORS.mutation : HEADER_COLORS.ast,
              model: st.model,
              slmRationale: `Role: ${st.role}. Dispatched to ${st.model}.`,
              inputs: [{ id: `in_${i}`, label: "Directive", color: SOCKET_COLORS.ast, shape: "circle" }],
              outputs: [{ id: `out_${i}`, label: "Result AST", color: SOCKET_COLORS.mutation, shape: "diamond" }],
              isGhost: true,
              isSelected: selectedNode?.id === subId
            }
          };
        });

        return [...mainNodes, previewPromptNode, ...previewSubNodes];
      }

      return mainNodes;
    });
  }, [activeWorkflowId, stepsData, isPlanPending, proposedSubtasks, totalPrompts, handleForkNode, handleRevertNode, setNodes]);

  // Update selection and revert highlight state without touching positions
  React.useEffect(() => {
    setNodes((prevNodes) =>
      prevNodes.map((n) => {
        const isSel = selectedNode?.id === n.id;
        const isRev = revertedIds.has(n.id);
        if (n.data?.isSelected === isSel && n.data?.isReverted === isRev) {
          return n;
        }
        return {
          ...n,
          data: {
            ...n.data,
            isSelected: isSel,
            isReverted: isRev
          }
        };
      })
    );
  }, [selectedNode, revertedIds, setNodes]);

  React.useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  // Handle Node Drag Stop: permanently remember position in stepsData so it never resets!
  const onNodeDragStop = useCallback((event, node) => {
    setStepsData((prev) =>
      prev.map((s) => (s.id === node.id ? { ...s, x: Math.round(node.position.x), y: Math.round(node.position.y) } : s))
    );
  }, []);

  // Handle Node Click (disambiguated from drag)
  const onNodeClick = useCallback((event, node) => {
    if (node.data?.isGhost) {
      if (node.id === "preview_prompt_root") {
        setSelectedNode({
          id: "preview_prompt_root",
          promptNum: totalPrompts + 1,
          title: `Prompt #${totalPrompts + 1} (Preview)`,
          promptText: userPromptInput,
          slmRationale: "Pending confirmation. Click 'Proceed' in the right window to deploy.",
          model: "Claude 3.5 Sonnet",
          agentName: "Orchestrator"
        });
      } else {
        setSelectedNode(node.data);
      }
      setSelectedEdge(null);
      setSidebarOpen(true);
      setSidebarTab("plan");
    } else {
      setSelectedNode(node.data);
      setSelectedEdge(null);
      setActivePrompt(node.data.promptNum);
      setSidebarOpen(true);
      setSidebarTab("node");
    }
  }, [totalPrompts, userPromptInput]);

  React.useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  // Handle Edge Click
  const onEdgeClick = useCallback((event, edge) => {
    event.stopPropagation();
    setSelectedEdge(edge.data);
    setSelectedNode(null);
    showToast(`Dispatched Job: ${edge.data.jobTitle}`);
  }, []);

  // Deploy Counterfactual Fork Branch
  const handleDeployFork = () => {
    if (!selectedNode) return;
    const newId = `fork_${Date.now().toString().slice(-4)}`;
    const forkedNode = {
      id: newId,
      promptNum: selectedNode.promptNum,
      agent: selectedNode.agent,
      type: "reasoning",
      title: `Forked: ${forkPromptInput.slice(0, 20)}...`,
      headerColor: HEADER_COLORS.reasoning,
      model: selectedNode.model,
      agentName: selectedNode.agentName,
      slmRationale: `Counterfactual branch spawned from Prompt #${selectedNode.promptNum}. Alternative constraints deployed without touching main worktree.`,
      promptText: forkPromptInput,
      inputs: selectedNode.inputs,
      outputs: selectedNode.outputs,
      tokens: { system: 15, files: 40, tools: 20, history: 25, count: 6800 },
      diff: null,
      x: selectedNode.x + 210,
      y: selectedNode.y + 110
    };

    setStepsData((prev) => [...prev, forkedNode]);
    setSelectedNode(forkedNode);
    setForkModalOpen(false);
    showToast(`Counterfactual branch deployed as node ${newId}!`);
  };

  return (
    <div className="flex h-screen w-screen flex-col bg-[#22201e] text-[#d8d3cd] select-none overflow-hidden">
      {/* 1. BLENDER TOP HEADER BAR */}
      <header className="flex h-7 shrink-0 items-center justify-between border-b border-[#262320] bg-[#282522] px-2 text-[11px] text-[#bda798] z-30">
        {/* Left: Blender Menus */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-medium">
            <span className="text-[#7a9a60] font-bold">CORTEX</span>
            <span className="text-[#665f57]">//</span>
            <span className="text-[#f5f0eb] font-semibold">Causa</span>
            <span className="text-[#8c8275] text-[9px]">v1.0</span>
          </div>

          <div className="h-3.5 w-px bg-[#3d3733]" />

          {/* Breadcrumb Selector */}
          <div className="flex items-center gap-1.5 rounded bg-[#1f1d1b] px-2 py-0.5 border border-[#1a1816]">
            <Layers size={11} className="text-[#7a9a60]" />
            <span className="text-[11px] font-medium text-[#f5f0eb]">Fullerence Causal Graph</span>
            <ChevronDown size={11} className="text-[#8c8275]" />
            <Shield size={10} className="text-[#8c8275] ml-1" />
            <span className="text-[9px] text-[#8c8275] font-mono">3 agents</span>
          </div>
        </div>

        {/* Right: Controls + "Enter Prompt" Button */}
        <div className="flex items-center gap-2">
          {/* USER REQUESTED FEATURE: "Enter Prompt" Button */}
          <button
            onClick={() => setIsEnterPromptModalOpen(true)}
            className="flex items-center gap-1.5 rounded bg-[#c86d3b] hover:bg-[#b35c2b] px-2.5 py-0.5 text-[10px] font-bold text-white shadow-sm border border-[#d97736]"
          >
            <PlusCircle size={11} />
            <span>Enter Prompt</span>
          </button>

          {/* Dedicated Blackboard Button */}
          <button
            onClick={() => setBlackboardOpen(true)}
            className="flex items-center gap-1 rounded bg-[#23201d] px-2 py-0.5 text-[10px] text-[#7a9a60] hover:text-white border border-[#1c1a18]"
          >
            <Database size={10} />
            <span>Blackboard</span>
          </button>

          {/* Per-Model Token Breakdown Dropdown */}
          <div className="relative">
            <button
              onClick={() => setTokenMenuOpen(!tokenMenuOpen)}
              className="flex items-center gap-1 rounded bg-[#23201d] px-2 py-0.5 font-mono text-[10px] text-[#d4a359] hover:text-white border border-[#1c1a18]"
            >
              <Zap size={10} />
              <span>197.0k tokens</span>
              <ChevronDown size={9} />
            </button>

            {tokenMenuOpen && (
              <div className="absolute right-0 top-6 z-50 w-72 rounded border border-[#3d3733] bg-[#2b2724] p-2.5 shadow-2xl">
                <div className="text-[10px] font-semibold text-[#f5f0eb] border-b border-[#36322e] pb-1.5 mb-2">
                  Per-Model Token Consumption
                </div>
                <div className="space-y-2">
                  {MODEL_TOKENS.map((m) => (
                    <div key={m.model}>
                      <div className="flex justify-between font-mono text-[9px]">
                        <span className="text-[#d8d3cd] font-semibold">{m.model}</span>
                        <span className="text-[#8c8275]">{m.tokens.toLocaleString()} ({m.percent}%)</span>
                      </div>
                      <div className="flex justify-between text-[8px] text-[#8c8275]">
                        <span>Agent: {m.agent}</span>
                        <span>Est: {m.cost}</span>
                      </div>
                      <div className="mt-0.5 h-1 w-full bg-[#1c1a18] rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${m.percent}%`, backgroundColor: m.color }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 text-[#8c8275]">
            <Magnet size={12} className="cursor-pointer hover:text-white" />
            <Eye size={12} className="cursor-pointer hover:text-white" />
          </div>

          {/* Toggle N-Panel Sidebar */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="flex items-center gap-1 rounded bg-[#23201d] px-1.5 py-0.5 text-[10px] text-[#a89f91] hover:text-white border border-[#1c1a18]"
            title="Toggle Properties Panel (N)"
          >
            <Sliders size={10} />
            <span>N-Panel</span>
          </button>
        </div>
      </header>

      {/* 1.5 WORKFLOW TAB MANAGEMENT STRIP */}
      <div className="flex h-7 shrink-0 items-center justify-between border-b border-[#262320] bg-[#1f1d1b] px-2 text-[10px] z-20 overflow-x-auto select-none">
        <div className="flex items-center gap-1">
          {workflows.map((wf) => {
            const isActive = wf.id === activeWorkflowId;
            return (
              <div
                key={wf.id}
                onClick={() => setActiveWorkflowId(wf.id)}
                className={`group relative flex items-center gap-1.5 rounded-t px-2.5 py-1 cursor-pointer transition-all border-t-2 ${
                  isActive
                    ? "bg-[#2b2724] text-white border-[#d97736] font-semibold shadow-sm"
                    : "bg-[#23201d] text-[#8c8275] border-transparent hover:bg-[#282522] hover:text-[#d8d3cd]"
                }`}
              >
                <GitBranch size={10} className={isActive ? "text-[#d97736]" : "text-[#8c8275]"} />
                <span className="truncate max-w-[140px]">{wf.title}</span>
                <span className="text-[8px] font-mono opacity-60">({wf.stepsData.length})</span>

                {workflows.length > 1 && (
                  <button
                    onClick={(e) => handleCloseWorkflowTab(wf.id, e)}
                    className="ml-1 text-[#8c8275] hover:text-[#b84a39] p-0.5 rounded transition"
                    title="Close workflow tab"
                  >
                    <X size={10} />
                  </button>
                )}
              </div>
            );
          })}

          {/* New Workflow Tab Button */}
          <button
            onClick={() => setIsNewWorkflowModalOpen(true)}
            className="flex items-center gap-1 rounded bg-[#2b2724] hover:bg-[#3d3733] px-2 py-0.5 text-[#d97736] font-bold text-[10px] border border-[#3d3733] transition ml-1"
            title="Create new workflow / conversation session"
          >
            <PlusCircle size={10} />
            <span>New Workflow</span>
          </button>
        </div>

        <div className="hidden md:flex items-center gap-2 text-[9px] font-mono text-[#8c8275]">
          <span className="text-[#a89f91]">Current Workspace:</span>
          <span className="text-[#f5f0eb] font-semibold">{activeWorkflow.title}</span>
          <span>•</span>
          <span>{workflows.length} Active Sessions</span>
        </div>
      </div>

      {/* 2. MAIN CANVAS WITH BLENDER WARM EARTH GRID */}
      <div className="flex min-h-0 flex-1 relative">
        <main className="relative min-w-0 flex-1 blender-canvas">
          {/* Agent Swimlane Legend Overlay */}
          <div className="pointer-events-none absolute left-3 top-3 z-10 flex gap-2">
            {AGENTS.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-1.5 rounded bg-[#23201d]/90 px-2 py-0.5 border border-[#3d3733] text-[9px] font-mono text-[#d8d3cd] shadow backdrop-blur pointer-events-auto"
              >
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: a.color }} />
                <span className="font-semibold">{a.name}</span>
                <span className="text-[#8c8275]">({a.model.split(" ")[0]})</span>
              </div>
            ))}
          </div>

          {/* SLM Reasoning Overlay Banner */}
          {isSlmThinking && (
            <div className="absolute left-1/2 top-4 z-30 -translate-x-1/2 rounded border border-[#d97736] bg-[#22201e]/95 px-4 py-2 text-[10px] shadow-2xl backdrop-blur flex items-center gap-2.5">
              <Sparkles size={13} className="text-[#d97736] animate-spin" />
              <div>
                <div className="font-bold text-[#f5f0eb]">Local SLM (Llama 3 8B) Reasoning...</div>
                <div className="text-[9px] text-[#bfa58a]">Decomposing objective & assigning sub-models across worktrees</div>
              </div>
            </div>
          )}

          {/* Edge Job Inspector Popover */}
          {selectedEdge && (
            <div className="absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded border border-[#d97736] bg-[#2b2724]/95 px-3.5 py-2 shadow-2xl text-[10px] max-w-sm backdrop-blur">
              <div className="flex items-center justify-between border-b border-[#3d3733] pb-1">
                <span className="font-bold text-[#d97736] uppercase tracking-wider text-[9px]">Dispatched Sub-Agent Task</span>
                <button onClick={() => setSelectedEdge(null)} className="text-[#8c8275] hover:text-white">
                  <X size={11} />
                </button>
              </div>
              <div className="mt-1 font-semibold text-[#f5f0eb]">{selectedEdge.jobTitle}</div>
              <div className="mt-0.5 text-[#c9c0b5]">
                <span className="text-[#8c8275]">Worker:</span> {selectedEdge.subAgent}
              </div>
              <div className="mt-0.5 text-[#c9c0b5]">
                <span className="text-[#8c8275]">SLM Reason:</span> {selectedEdge.jobReason}
              </div>
              <div className="mt-1 rounded bg-[#1c1a18] p-1 font-mono text-[8px] text-[#7a9a60] border border-[#262320]">
                Payload: {selectedEdge.payload}
              </div>
            </div>
          )}

          {/* ReactFlow Canvas */}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onEdgeClick={onEdgeClick}
            onNodeClick={onNodeClick}
            onNodeDragStop={onNodeDragStop}
            nodesDraggable={true}
            elementsSelectable={true}
            fitView
            fitViewOptions={{ padding: 0.15, minZoom: 0.35, maxZoom: 1.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Controls position="bottom-left" showInteractive={false} />
            <MiniMap
              position="bottom-right"
              nodeColor={(n) => n.data?.headerColor || "#4e4842"}
              maskColor="rgba(34,32,30,0.85)"
            />
          </ReactFlow>

          {/* Toast Notification */}
          {toast && (
            <div className="absolute bottom-4 left-1/2 z-50 -translate-x-1/2 rounded border border-[#d97736] bg-[#2b2724] px-3 py-1.5 font-mono text-[9px] text-[#d97736] shadow-2xl">
              {toast}
            </div>
          )}
        </main>

        {/* 3. BLENDER "N-PANEL" (PROPERTIES & SLM PLAN REVIEW DRAWER) */}
        {sidebarOpen && (
          <aside className="w-[350px] shrink-0 border-l border-[#262320] bg-[#2b2724] flex flex-col z-20 text-[11px]">
            {/* Sidebar Tabs */}
            <div className="flex h-7 border-b border-[#262320] bg-[#22201e] text-[10px]">
              {isPlanPending && (
                <button
                  onClick={() => setSidebarTab("plan")}
                  className={`flex-1 py-1 text-center font-bold text-[#d97736] ${sidebarTab === "plan" ? "bg-[#2b2724] border-t-2 border-[#d97736]" : "text-[#d8d3cd]"}`}
                >
                  ⚡ SLM Plan Review
                </button>
              )}
              {[
                ["slm", "SLM Rationale"],
                ["node", "Prompt & Node"],
                ["diff", "Worktree Diff"]
              ].map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => setSidebarTab(k)}
                  className={`flex-1 py-1 text-center font-medium ${sidebarTab === k ? "bg-[#2b2724] text-white border-t border-[#d97736]" : "text-[#8c8275] hover:text-[#c9c0b5]"}`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Sidebar Content */}
            <div className="flex-1 overflow-auto p-3 space-y-3">
              {/* TAB 0: SLM PLAN REVIEW & PROCEED WINDOW */}
              {sidebarTab === "plan" && isPlanPending && (
                <div className="space-y-3">
                  <div className="rounded border border-[#d97736] bg-[#2f2823] p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#d97736] text-[11px]">Proposed Swarm Dispatch</span>
                      <span className="rounded bg-[#d97736]/20 px-1.5 py-0.5 text-[8px] font-mono text-[#d4a359] border border-[#d97736]/40">
                        Prompt #{totalPrompts + 1}
                      </span>
                    </div>
                    <div className="mt-1 text-[10px] text-[#c9c0b5]">
                      SLM decomposed the objective into 3 sub-agent roles. You can edit their prompts or models before proceeding.
                    </div>
                  </div>

                  {/* Primary Objective Preview */}
                  <div className="border border-[#3d3733] bg-[#1f1d1b] rounded p-2 text-[10px]">
                    <div className="text-[#8c8275] font-bold uppercase text-[9px] mb-1">Target Swarm Objective:</div>
                    <div className="text-[#f5f0eb] font-mono leading-relaxed">{userPromptInput}</div>
                  </div>

                  {/* Editable Sub-model Roles */}
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold text-[#8c8275] uppercase tracking-wider">
                      Sub-Model Role Assignments:
                    </div>

                    {proposedSubtasks.map((st, i) => (
                      <div key={st.id} className="border border-[#3d3733] bg-[#1f1d1b] rounded p-2 space-y-1.5 text-[10px]">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[#d4a359]">{st.agentName}</span>
                          <select
                            value={st.model}
                            onChange={(e) => {
                              const next = [...proposedSubtasks];
                              next[i].model = e.target.value;
                              setProposedSubtasks(next);
                            }}
                            className="blender-select text-[9px] font-mono"
                          >
                            <option>Claude 3.5 Sonnet</option>
                            <option>GPT-4o</option>
                            <option>Gemini 1.5 Pro</option>
                            {st.model && !["Claude 3.5 Sonnet", "GPT-4o", "Gemini 1.5 Pro"].includes(st.model) && (
                              <option>{st.model}</option>
                            )}
                            <option>gemma3:latest (Local SLM)</option>
                          </select>
                        </div>
                        <div className="text-[9px] text-[#8c8275]">Role: <span className="text-white">{st.role}</span></div>

                        {/* Editable prompt textarea */}
                        <div>
                          <label className="text-[8px] text-[#8c8275] uppercase">Assigned Sub-Prompt:</label>
                          <textarea
                            rows={2}
                            value={st.prompt}
                            onChange={(e) => {
                              const next = [...proposedSubtasks];
                              next[i].prompt = e.target.value;
                              setProposedSubtasks(next);
                            }}
                            className="w-full mt-0.5 rounded bg-[#161412] border border-[#3d3733] p-1.5 text-[9px] font-mono text-white focus:border-[#d97736] outline-none"
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Action Buttons: PROCEED / DISCARD */}
                  <div className="pt-2 space-y-1.5 border-t border-[#3d3733]">
                    <button
                      onClick={handleProceedPlan}
                      className="w-full flex items-center justify-center gap-1.5 rounded bg-[#c86d3b] hover:bg-[#b35c2b] text-white py-2 text-[11px] font-bold shadow-lg border border-[#d97736]"
                    >
                      <Play size={12} fill="currentColor" />
                      <span>Proceed & Execute Swarm Plan</span>
                    </button>
                    <button
                      onClick={handleDiscardPlan}
                      className="w-full flex items-center justify-center gap-1 rounded bg-[#23201d] hover:bg-[#3d3733] text-[#a89f91] py-1 text-[10px]"
                    >
                      <X size={11} />
                      <span>Discard Preview</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Tab 1: SLM Rationale & Model Choice */}
              {sidebarTab === "slm" && (
                <div className="space-y-3">
                  <div className="border border-[#3d3733] bg-[#23201d] rounded p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-bold uppercase text-[#8c8275]">Assigned Model</span>
                      <span className="text-[#d4a359] font-mono font-bold">{selectedNode?.model}</span>
                    </div>
                    <div className="mt-1 text-[10px] text-[#c9c0b5]">
                      <span className="text-[#8c8275]">Sub-Agent:</span> {selectedNode?.agentName}
                    </div>
                  </div>

                  {/* Why this model was chosen by SLM */}
                  <div className="border border-[#3d3733] bg-[#23201d] rounded p-2.5">
                    <div className="flex items-center gap-1.5 text-[#7a9a60] font-bold text-[10px] mb-2">
                      <Sparkles size={12} />
                      <span>Why this model was chosen by the SLM:</span>
                    </div>
                    <div className="text-[10px] leading-relaxed text-[#d8d3cd] bg-[#1a1816] p-2.5 rounded border border-[#262320]">
                      {selectedNode?.slmRationale}
                    </div>
                  </div>

                  {/* Routing Telemetry */}
                  <div className="border border-[#3d3733] bg-[#23201d] rounded p-2.5 space-y-1 text-[10px]">
                    <div className="text-[#8c8275] font-bold uppercase text-[9px]">Routing Telemetry</div>
                    <div className="flex justify-between font-mono">
                      <span className="text-[#a89f91]">Action Type:</span>
                      <span className="text-white capitalize">{selectedNode?.type}</span>
                    </div>
                    <div className="flex justify-between font-mono">
                      <span className="text-[#a89f91]">Tokens Processed:</span>
                      <span className="text-white">{selectedNode?.tokens?.count?.toLocaleString() || "7,400"} tok</span>
                    </div>
                    <div className="flex justify-between font-mono">
                      <span className="text-[#a89f91]">Pre-Commit Gate:</span>
                      <span className="text-[#7a9a60]">Deterministic Approved</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Prompt & Node Info */}
              {sidebarTab === "node" && (
                <div className="space-y-3">
                  <div className="border border-[#3d3733] bg-[#23201d] rounded p-2.5 space-y-1">
                    <div className="text-[10px] font-bold text-[#8c8275] uppercase">Prompt Directive #{selectedNode?.promptNum}</div>
                    <div className="text-[12px] font-semibold text-white">{selectedNode?.title}</div>
                    <div className="text-[10px] leading-relaxed text-[#c9c0b5] font-mono bg-[#1a1816] p-2 rounded border border-[#262320] mt-1.5">
                      {selectedNode?.promptText}
                    </div>
                  </div>

                  {/* Token Breakdown Bar */}
                  <div className="border border-[#3d3733] bg-[#23201d] rounded p-2.5">
                    <div className="text-[9px] font-bold text-[#8c8275] uppercase mb-1.5">Token Distribution</div>
                    <div className="flex h-1.5 w-full rounded-full overflow-hidden bg-[#1a1816]">
                      <div className="bg-[#d4a359]" style={{ width: `${selectedNode?.tokens?.system || 15}%` }} title="System" />
                      <div className="bg-[#7a9a60]" style={{ width: `${selectedNode?.tokens?.files || 45}%` }} title="Files" />
                      <div className="bg-[#8c7a6b]" style={{ width: `${selectedNode?.tokens?.tools || 20}%` }} title="Tools" />
                      <div className="bg-[#b86b53]" style={{ width: `${selectedNode?.tokens?.history || 20}%` }} title="History" />
                    </div>
                    <div className="mt-2 grid grid-cols-4 gap-1 text-[8px] font-mono text-[#8c8275]">
                      <span>Sys: {selectedNode?.tokens?.system || 15}%</span>
                      <span>Files: {selectedNode?.tokens?.files || 45}%</span>
                      <span>Tools: {selectedNode?.tokens?.tools || 20}%</span>
                      <span>Hist: {selectedNode?.tokens?.history || 20}%</span>
                    </div>
                  </div>

                  {/* Actions */}
                  {selectedNode && !selectedNode.isGhost && (
                    <div className="pt-2 space-y-1.5">
                      <button
                        onClick={() => handleForkNode(selectedNode)}
                        className="w-full flex items-center justify-center gap-1.5 rounded bg-[#3d3733] hover:bg-[#4d4641] text-[#d8d3cd] hover:text-white py-1.5 text-[10px] font-medium border border-[#4e4842]"
                      >
                        <GitFork size={12} className="text-[#d4a359]" />
                        <span>Fork Counterfactual Branch</span>
                      </button>
                      <button
                        onClick={() => handleRevertNode(selectedNode)}
                        className="w-full flex items-center justify-center gap-1.5 rounded bg-[#36211e] hover:bg-[#482824] text-[#b84a39] py-1.5 text-[10px] font-medium border border-[#5c2a23]"
                      >
                        <Trash2 size={12} />
                        <span>Delete & Revert Prompt #{selectedNode.promptNum}</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: Worktree Diff */}
              {sidebarTab === "diff" && (
                <div>
                  {selectedNode?.diff ? (
                    <div className="border border-[#3d3733] bg-[#1a1816] rounded overflow-hidden">
                      <div className="bg-[#22201e] px-2 py-1 text-[9px] font-mono text-[#8c8275] border-b border-[#262320]">
                        Unified Worktree Diff: schema.prisma
                      </div>
                      <pre className="p-2 font-mono text-[9px] leading-relaxed overflow-x-auto text-[#d8d3cd]">
                        {selectedNode.diff.split("\n").map((line, idx) => (
                          <div
                            key={idx}
                            className={line.startsWith("+") ? "bg-[#243322] text-[#7a9a60]" : line.startsWith("-") ? "bg-[#38201d] text-[#b84a39]" : "text-[#8c8275]"}
                          >
                            {line}
                          </div>
                        ))}
                      </pre>
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[10px] text-[#8c8275] border border-dashed border-[#3d3733] rounded">
                      No filesystem mutations logged at this step (pure reasoning or read tool call).
                    </div>
                  )}
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* 4. BLENDER BOTTOM STATUS BAR & PROMPT STEPPER */}
      <footer className="h-6 shrink-0 border-t border-[#262320] bg-[#282522] px-3 flex items-center justify-between text-[10px] text-[#8c8275] z-30 font-mono">
        {/* Left: Blender Mouse Action Hints */}
        <div className="flex items-center gap-4">
          <span className="text-[#d8d3cd]">Causa Swarm Active</span>
          <div className="hidden sm:flex items-center gap-3 text-[#8c8275]">
            <span>🖱 Select Node / Edge</span>
            <span>🖱 Pan View</span>
            <span>🖱 Context Actions</span>
          </div>
        </div>

        {/* Center/Right: Prompt-Indexed Stepper Controls */}
        <div className="flex items-center gap-2">
          <span className="text-[#a89f91]">Prompt:</span>
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPrompts }, (_, i) => i + 1).map((num) => (
              <button
                key={num}
                onClick={() => {
                  setActivePrompt(num);
                  const node = stepsData.find((s) => s.promptNum === num);
                  if (node) setSelectedNode(node);
                }}
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${activePrompt === num ? "bg-[#c86d3b] text-white" : "bg-[#23201d] text-[#8c8275] hover:text-white"}`}
              >
                #{num}
              </button>
            ))}
          </div>

          <div className="h-3 w-px bg-[#3d3733] mx-1" />

          {/* Run / Step Controls */}
          <button
            onClick={() => setPaused(!paused)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold ${paused ? "bg-[#4e6e44] text-white" : "bg-[#23201d] text-[#d8d3cd] hover:text-white"}`}
          >
            {paused ? <Play size={9} fill="currentColor" /> : <Pause size={9} />}
            <span>{paused ? "Run" : "Pause"}</span>
          </button>
          <button
            onClick={() => {
              const next = Math.min(totalPrompts, activePrompt + 1);
              setActivePrompt(next);
              const node = stepsData.find((s) => s.promptNum === next);
              if (node) setSelectedNode(node);
            }}
            className="flex items-center gap-0.5 px-2 py-0.5 rounded bg-[#23201d] text-[#d8d3cd] hover:text-white text-[9px]"
          >
            <span>Step</span>
            <ChevronRight size={10} />
          </button>
        </div>
      </footer>

      {/* MODAL 1: ENTER PROMPT */}
      {isEnterPromptModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded border border-[#4e4842] bg-[#2b2724] p-3.5 shadow-2xl text-[11px]">
            <div className="flex items-center justify-between border-b border-[#3d3733] pb-2 font-bold text-white">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-[#d97736]" />
                <span>Enter Swarm Prompt / Directive</span>
              </div>
              <X size={12} className="cursor-pointer text-[#8c8275] hover:text-white" onClick={() => setIsEnterPromptModalOpen(false)} />
            </div>

            <div className="mt-2.5">
              <label className="text-[10px] text-[#a89f91]">New Swarm Task / Codebase Mutation Objective:</label>
              <textarea
                rows={4}
                value={userPromptInput}
                onChange={(e) => setUserPromptInput(e.target.value)}
                placeholder="Enter objective for the swarm to execute..."
                className="mt-1.5 w-full rounded bg-[#1a1816] border border-[#3d3733] p-2.5 text-[10px] text-white font-mono focus:border-[#d97736] outline-none"
              />
              <div className="mt-1 text-[9px] text-[#8c8275]">
                The Local SLM will analyze this prompt, partition it across Orchestrator, Auth-Worker, and DB-Migration, and display a dashed preview graph.
              </div>
            </div>

            <div className="mt-3.5 flex justify-end gap-2 border-t border-[#3d3733] pt-2.5">
              <button
                onClick={() => setIsEnterPromptModalOpen(false)}
                className="px-2.5 py-1 rounded bg-[#3d3733] text-[#a89f91] hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleStartPromptDecomposition}
                className="flex items-center gap-1.5 px-3.5 py-1 rounded bg-[#c86d3b] text-white font-bold hover:bg-[#b35c2b] shadow border border-[#d97736]"
              >
                <Sparkles size={11} />
                <span>Submit to Local SLM</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: FORK COUNTERFACTUAL BRANCH */}
      {forkModalOpen && selectedNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded border border-[#4e4842] bg-[#2b2724] p-3 shadow-2xl text-[11px]">
            <div className="flex items-center justify-between border-b border-[#3d3733] pb-2 font-bold text-white">
              <span>Fork Counterfactual Branch from Prompt #{selectedNode.promptNum}</span>
              <X size={12} className="cursor-pointer text-[#8c8275] hover:text-white" onClick={() => setForkModalOpen(false)} />
            </div>
            <div className="mt-2.5">
              <label className="text-[10px] text-[#a89f91]">Modify Prompt Premise / Inject Constraint:</label>
              <textarea
                rows={3}
                defaultValue={`Counterfactual from Prompt #${selectedNode.promptNum}: `}
                onChange={(e) => setForkPromptInput(e.target.value)}
                className="mt-1 w-full rounded bg-[#1a1816] border border-[#3d3733] p-2 text-[10px] text-white font-mono focus:border-[#d97736] outline-none"
              />
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => setForkModalOpen(false)}
                className="px-2.5 py-1 rounded bg-[#3d3733] text-[#a89f91] hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleDeployFork}
                className="px-3 py-1 rounded bg-[#c86d3b] text-white font-bold hover:bg-[#b35c2b]"
              >
                Deploy Fork
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: DEDICATED BLACKBOARD VIEW */}
      {blackboardOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs">
          <div className="w-full max-w-xl rounded border border-[#4e4842] bg-[#2b2724] p-3 shadow-2xl text-[11px]">
            <div className="flex items-center justify-between border-b border-[#3d3733] pb-2 font-bold text-white">
              <div className="flex items-center gap-1.5">
                <Database size={12} className="text-[#7a9a60]" />
                <span>Shared SQLite Blackboard (Ferry Engine)</span>
              </div>
              <X size={12} className="cursor-pointer text-[#8c8275] hover:text-white" onClick={() => setBlackboardOpen(false)} />
            </div>
            <div className="mt-2.5 overflow-hidden rounded border border-[#3d3733]">
              <table className="w-full text-left font-mono text-[9px]">
                <thead className="bg-[#1f1d1b] text-[#8c8275] uppercase text-[8px] border-b border-[#3d3733]">
                  <tr>
                    <th className="p-2">Contract Interface</th>
                    <th className="p-2">Holder Agent</th>
                    <th className="p-2">Access</th>
                    <th className="p-2">Version</th>
                    <th className="p-2">Lock Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#262320] text-[#d8d3cd]">
                  {telemetry.contracts && telemetry.contracts.length > 0 ? (
                    telemetry.contracts.map((c, idx) => {
                      const matchedLease = telemetry.leases?.find((l) => l.file_path === c.file_path);
                      return (
                        <tr key={c.id || idx}>
                          <td className="p-2 text-[#7a9a60]">{c.symbol_id || c.name}</td>
                          <td className="p-2">{c.agent_id || "Agent"}</td>
                          <td className="p-2 text-[#d4a359]">{matchedLease?.lock_type || "READ"}</td>
                          <td className="p-2">v1.0</td>
                          <td className={`p-2 font-semibold ${matchedLease?.lock_type === "WRITE" ? "text-[#d97736]" : "text-[#8c8275]"}`}>
                            {matchedLease ? (matchedLease.lock_type === "WRITE" ? "EXCLUSIVE LOCK" : "Shared Lease") : "Active Contract"}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <>
                      <tr>
                        <td className="p-2 text-[#7a9a60]">session.contract</td>
                        <td className="p-2">Auth-Worker (GPT-4o)</td>
                        <td className="p-2 text-[#7a9a60]">READ</td>
                        <td className="p-2">v2.1</td>
                        <td className="p-2 text-[#8c8275]">Shared</td>
                      </tr>
                      <tr>
                        <td className="p-2 text-[#7a9a60]">prisma.schema.Session</td>
                        <td className="p-2">DB-Migration (Gemini 1.5 Pro)</td>
                        <td className="p-2 text-[#d4a359]">WRITE</td>
                        <td className="p-2">v2.0</td>
                        <td className="p-2 text-[#d97736] font-semibold">EXCLUSIVE LOCK</td>
                      </tr>
                      <tr>
                        <td className="p-2 text-[#7a9a60]">auth.adapter.lookup</td>
                        <td className="p-2">Auth-Worker (GPT-4o)</td>
                        <td className="p-2 text-[#d4a359]">WRITE</td>
                        <td className="p-2">v1.2</td>
                        <td className="p-2 text-[#8c8275]">Pending Commit</td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                onClick={() => setBlackboardOpen(false)}
                className="px-3 py-1 rounded bg-[#3d3733] text-white hover:bg-[#4d4641]"
              >
                Close Blackboard
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: CREATE NEW WORKFLOW / CONVERSATION */}
      {isNewWorkflowModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded border border-[#4e4842] bg-[#2b2724] p-3.5 shadow-2xl text-[11px]">
            <div className="flex items-center justify-between border-b border-[#3d3733] pb-2 font-bold text-white">
              <div className="flex items-center gap-1.5">
                <GitBranch size={13} className="text-[#d97736]" />
                <span>Create New Conversation / Workflow Session</span>
              </div>
              <X size={12} className="cursor-pointer text-[#8c8275] hover:text-white" onClick={() => setIsNewWorkflowModalOpen(false)} />
            </div>

            <div className="mt-3 space-y-3">
              <div>
                <label className="text-[10px] text-[#a89f91] font-medium">Workflow Session Title:</label>
                <input
                  type="text"
                  value={newWfTitleInput}
                  onChange={(e) => setNewWfTitleInput(e.target.value)}
                  placeholder="e.g. JWT Token Refresh Pipeline"
                  className="mt-1 w-full rounded bg-[#1a1816] border border-[#3d3733] p-2 text-[10px] text-white font-mono focus:border-[#d97736] outline-none"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#a89f91] font-medium">Starter Workflow Template:</label>
                <select
                  value={newWfTemplateType}
                  onChange={(e) => setNewWfTemplateType(e.target.value)}
                  className="mt-1 w-full rounded bg-[#1a1816] border border-[#3d3733] p-2 text-[10px] text-white font-mono cursor-pointer"
                >
                  <option value="blank">Blank Workflow Canvas (Fresh Directive Node)</option>
                  <option value="oauth">OAuth2 & Session Refactor (Full 7 Steps)</option>
                  <option value="stripe">Stripe Webhook Verification (2 Steps)</option>
                </select>
              </div>

              <div className="text-[9px] text-[#8c8275] bg-[#1a1816] p-2 rounded border border-[#262320]">
                Each workflow runs in an isolated causal graph space. You can switch between tabs anytime without losing node positions or SLM plan states.
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2 border-t border-[#3d3733] pt-2.5">
              <button
                onClick={() => setIsNewWorkflowModalOpen(false)}
                className="px-2.5 py-1 rounded bg-[#3d3733] text-[#a89f91] hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateWorkflow}
                className="flex items-center gap-1 px-3.5 py-1 rounded bg-[#c86d3b] text-white font-bold hover:bg-[#b35c2b] shadow border border-[#d97736]"
              >
                <PlusCircle size={11} />
                <span>Create Workflow Tab</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



