"""Causa / Fullerenes unified command line interface."""

import argparse
import sys
from packages.cli.commands.log import cmd_log
from packages.cli.commands.blame import cmd_blame
from packages.cli.commands.rollback import cmd_rollback
from packages.cli.commands.inspect import cmd_inspect
from packages.cli.mcp.server import CausaMCPServer


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser."""
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

    # fullerenes log [sessionId]
    sub_log = subparsers.add_parser("log", help="Render visual causal execution tree")
    sub_log.add_argument("sessionId", nargs="?", default="default", help="Session ID to render")

    # fullerenes blame <failedNodeId>
    sub_blame = subparsers.add_parser("blame", help="Localize first-bad-decision root cause")
    sub_blame.add_argument("failedNodeId", help="Node ID of failure or test run")

    # fullerenes rollback <nodeId>
    sub_rb = subparsers.add_parser("rollback", help="Compute blast radius and generate Git rollback script")
    sub_rb.add_argument("nodeId", help="Corrupted or diverging node ID")

    # fullerenes inspect <nodeId>
    sub_insp = subparsers.add_parser("inspect", help="Display token context attribution slices")
    sub_insp.add_argument("nodeId", help="Node ID to inspect")

    # fullerenes mcp
    subparsers.add_parser("mcp", help="Run the Model Context Protocol (MCP) server")

    return parser


def main(argv=None) -> int:
    """Main CLI entrypoint."""
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
        # Stdio loop for MCP JSON-RPC
        server = CausaMCPServer(db_path=args.db)
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
