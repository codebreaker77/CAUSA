"""Canonical workspace boundaries shared by API and tool execution."""

from pathlib import Path, PureWindowsPath


def workspace_path(root, relative, allow_root=False):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
        raise ValueError("A non-empty relative workspace path is required")
    relative = relative.replace("\\", "/")
    windows = PureWindowsPath(relative)
    if windows.drive or windows.root or Path(relative).is_absolute():
        raise ValueError("Absolute workspace paths are forbidden")
    if ".." in relative.split("/"):
        raise ValueError("Workspace traversal is forbidden")
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Path resolves outside the workspace") from None
    if target == root and not allow_root:
        raise ValueError("Path must identify a file or child directory")
    return target


def public_source_path(relative):
    parts = relative.replace("\\", "/").split("/")
    return not any(p.startswith(".") or p in {"node_modules", "__pycache__", "dist", "build"}
                   for p in parts)
