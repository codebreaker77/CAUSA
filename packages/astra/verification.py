"""Verification with explicit evidence; missing tooling never means success."""

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from packages.paths import workspace_path


@dataclass
class VerificationResult:
    passed: bool
    level: str
    log: str


def execution_env():
    # Never pass provider credentials to generated tests or builds.
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
               "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def run_check(argv, root, timeout=60):
    try:
        result = subprocess.run(argv, cwd=root, env=execution_env(), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return VerificationResult(result.returncode == 0, "tests", (result.stdout + result.stderr)[-20000:])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return VerificationResult(False, "tests", str(exc))


def verify_files(root, paths: List[str], run_tests=True):
    logs = []
    levels = set()
    for relative in paths:
        try:
            target = workspace_path(root, relative)
            content = target.read_text(encoding="utf-8")
            ext = target.suffix.lower()
            if ext in {".py", ".pyw"}:
                ast.parse(content, filename=relative)
                levels.add("syntax")
            elif ext == ".json":
                json.loads(content)
                levels.add("syntax")
            elif ext in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
                node = shutil.which("node")
                if not node:
                    return VerificationResult(False, "syntax", "Node.js is required for source validation")
                script = Path(__file__).resolve().parents[2] / "scripts" / "verify_source.cjs"
                result = run_check([node, str(script), str(target)], root)
                if not result.passed:
                    return VerificationResult(False, "syntax", result.log)
                levels.add("types" if ext in {".ts", ".tsx"} else "syntax")
            else:
                levels.add("content")
            logs.append(f"Validated {relative}")
        except (ValueError, OSError, SyntaxError) as exc:
            return VerificationResult(False, "syntax", str(exc))
    if run_tests:
        root = Path(root)
        python_tests = [p for p in root.rglob("test_*.py")
                        if not any(part.startswith(".") or part == "node_modules"
                                   for part in p.relative_to(root).parts)]
        if python_tests:
            result = run_check([sys.executable, "-m", "pytest", "-q", "--import-mode=importlib",
                                *[str(p.relative_to(root)) for p in python_tests]], root)
            if not result.passed:
                return result
            logs.append(result.log)
            levels.add("tests")
    level = "tests" if "tests" in levels else "types" if "types" in levels else "syntax" if "syntax" in levels else "content"
    return VerificationResult(True, level, "\n".join(logs))
