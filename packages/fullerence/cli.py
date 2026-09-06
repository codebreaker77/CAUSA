"""Causa / Fullerence CLI commands and main entrypoint."""

import argparse
import sys
from typing import Dict, Any, List, Optional
from packages.fullerence.types import CausalNode
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.fullerence.debugger import (
    localize_first_bad_decision,
    compute_counterfactual_fork_point,
    get_transitive_taint_set,
    get_attribution_view,
)
from packages.fullerence.mcp import FullerenceMCPServer


# -------------------------------------------------------------
# 1. fullerenes log [sessionId]
# -------------------------------------------------------------
def format_causal_tree(nodes: List[CausalNode]) -> str:
    """Formats a list of causal execution nodes into a human-readable visual ASCII tree."""
    if not nodes:
        return "No causal execution nodes recorded for this session."

    lines: List[str] = ["\n=== CAUSAL EXECUTION GRAPH ==="]
    sorted_nodes = sorted(nodes, key=lambda n: n.created_at)

    for i, node in enumerate(sorted_nodes):
        prefix = "+-- " if i < len(sorted_nodes) - 1 else "\\-- "
        status_icon = "[OK]" if node.status in ("success", "committed", "completed") else "[FAIL]"
        tool_info = f" -> {node.tool_name}" if node.tool_name else ""
        agent_info = f"[{node.agent_id}]" if node.agent_id else "[unknown]"
        worktree_info = f" ({node.worktree_path})" if node.worktree_path else ""

        line = f"{prefix}{status_icon} Node: {node.id} {agent_info}{tool_info}{worktree_info}"
        lines.append(line)

        if node.prompt_snapshot:
            snippet = node.prompt_snapshot.strip().replace("\n", " ")[:60]
            lines.append(f"    |   Prompt: \"{snippet}...\"")
        elif node.metadata:
            snippet = str(node.metadata)[:60]
            lines.append(f"    |   Detail: {snippet}")

    lines.append("==============================\n")
    return "\n".join(lines)


def cmd_log(session_id: str, db_path: str = "graph.db") -> str:
    storage = FullerenceStorage(db_path=db_path)
    nodes = storage.get_session_nodes(session_id)
    return format_causal_tree(nodes)


# -------------------------------------------------------------
# 2. fullerenes blame <failedNodeId>
# -------------------------------------------------------------
def format_blame_diagnosis(diagnosis: Dict[str, Any]) -> str:
    lines: List[str] = [
        "\n================ FIRST-BAD-DECISION BLAME ================",
        f"  Failed Node ID      : {diagnosis.get('failure_node_id') or diagnosis.get('failed_node_id')}",
        f"  Root Cause Node ID  : {diagnosis['root_cause_node_id']}",
        f"  Faulty Agent ID     : {diagnosis['faulty_agent_id']}",
        f"  Divergence Reason   : {diagnosis['divergence_reason']}",
        f"  Causal Trail        : {' <-- '.join(diagnosis['causal_path'])}",
        "=========================================================\n",
    ]
    return "\n".join(lines)


def cmd_blame(failed_node_id: str, db_path: str = "graph.db") -> str:
    storage = FullerenceStorage(db_path=db_path)
    graph = FullerenceGraph(storage)
    diagnosis = localize_first_bad_decision(storage, graph, failed_node_id)
    return format_blame_diagnosis(diagnosis)


# -------------------------------------------------------------
# 3. fullerenes rollback <nodeId>
# -------------------------------------------------------------
def format_rollback_plan(plan: Dict[str, Any], taint: Dict[str, Any]) -> str:
    lines: List[str] = [
        "\n================ COUNTERFACTUAL ROLLBACK PLAN ================",
        f"  Corrupt Node ID       : {plan['corrupt_node_id']}",
        f"  Clean Ancestor Node   : {plan['clean_ancestor_node_id']}",
        f"  Clean Git Checkpoint  : {plan['clean_git_commit_hash']}",
        f"  Target Worktree       : {plan['target_worktree_path']}",
        "",
        "--- BLAST RADIUS INVENTORY ---",
        f"  Tainted Agents        : {', '.join(taint['tainted_agent_ids'])}",
        f"  Tainted Worktrees     : {', '.join(taint['tainted_worktree_paths'])}",
        f"  Contaminated Files    : {', '.join(taint['contaminated_files']) if taint['contaminated_files'] else 'None'}",
        f"  Total Nodes Invalidated: {taint['total_tainted_count']}",
        "",
        "--- SUGGESTED PROMPT CONSTRAINT ---",
        f"  {plan['suggested_correction_constraint']}",
        "",
        "--- EXECUTABLE GIT ROLLBACK SCRIPT ---",
        f"  $ {plan['reset_command']}",
        "==============================================================\n",
    ]
    return "\n".join(lines)


def cmd_rollback(corrupt_node_id: str, db_path: str = "graph.db") -> str:
    storage = FullerenceStorage(db_path=db_path)
    graph = FullerenceGraph(storage)
    plan = compute_counterfactual_fork_point(storage, graph, corrupt_node_id)
    taint = get_transitive_taint_set(storage, graph, corrupt_node_id)
    return format_rollback_plan(plan, taint)


# -------------------------------------------------------------
# 4. fullerenes inspect <nodeId>
# -------------------------------------------------------------
def format_attribution_view(view: Dict[str, Any]) -> str:
    slices = view.get("active_context_slices", [])
    prompt_len = len(view.get("full_prompt") or "")

    lines: List[str] = [
        "\n================ TOKEN CONTEXT ATTRIBUTION ================",
        f"  Node ID           : {view['node_id']}",
        f"  Agent ID          : {view['agent_id']}",
        f"  Step Type         : {view['step_type']}",
        f"  Prompt Length     : {prompt_len} chars",
        "",
        "--- ACTIVE CONTEXT SLICES ---",
    ]

    for s in slices:
        stype = s.get("type", "unknown").upper()
        source = s.get("source", "")
        excerpt = s.get("excerpt", "")[:60].replace("\n", " ")
        lines.append(f"  [{stype:<22}] ({source}) | \"{excerpt}...\"")

    lines.append("===========================================================\n")
    return "\n".join(lines)


def cmd_inspect(node_id: str, db_path: str = "graph.db") -> str:
    storage = FullerenceStorage(db_path=db_path)
    view = get_attribution_view(storage, node_id)
    return format_attribution_view(view)


# -------------------------------------------------------------
# 5. CLI Parser & Entry Point
# -------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fullerenes",
        description="Causa / Fullerenes Causal Substrate & Debugger CLI",
    )
    parser.add_argument(
        "--db",
        default="graph.db",
        help="Path to SQLite graph database (default: graph.db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    sub_log = subparsers.add_parser("log", help="Render visual causal execution tree")
    sub_log.add_argument("sessionId", nargs="?", default="default", help="Session ID to render")

    sub_blame = subparsers.add_parser("blame", help="Localize first-bad-decision root cause")
    sub_blame.add_argument("failedNodeId", help="Node ID of failure or test run")

    sub_rb = subparsers.add_parser("rollback", help="Compute blast radius and generate Git rollback script")
    sub_rb.add_argument("nodeId", help="Corrupted or diverging node ID")

    sub_insp = subparsers.add_parser("inspect", help="Display token context attribution slices")
    sub_insp.add_argument("nodeId", help="Node ID to inspect")

    subparsers.add_parser("mcp", help="Run the Model Context Protocol (MCP) server")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "log":
        out = cmd_log(args.sessionId, db_path=args.db)
        print(out)
    elif args.command == "blame":
        out = cmd_blame(args.failedNodeId, db_path=args.db)
        print(out)
    elif args.command == "rollback":
        out = cmd_rollback(args.nodeId, db_path=args.db)
        print(out)
    elif args.command == "inspect":
        out = cmd_inspect(args.nodeId, db_path=args.db)
        print(out)
    elif args.command == "mcp":
        server = FullerenceMCPServer(db_path=args.db)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            resp = server.handle_rpc_request(line)
            sys.stdout.write(resp + "\n")
            sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
