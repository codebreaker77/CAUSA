"""Noninteractive CLI using the same runtime as the HTTP API."""

import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from packages.astra.planner import TaskPlan
from packages.astra.runtime import ExecutionRuntime
from packages.gemini.client import GeminiClient


def main():
    parser = argparse.ArgumentParser(description="Execute a typed Causa task plan")
    parser.add_argument("--plan", required=True, help="JSON matching the TaskPlan schema")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--preview", action="store_true", help="Keep outputs isolated")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    load_dotenv()
    plan = TaskPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    runtime = ExecutionRuntime(Path(args.workspace) / ".causa")
    result = runtime.execute(plan, args.workspace, GeminiClient(), max_workers=args.workers,
                             apply=not args.preview)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
