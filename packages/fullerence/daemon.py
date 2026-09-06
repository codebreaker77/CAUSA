"""Multi-worktree dynamic file watcher and shared blackboard synchronization."""

from packages.daemon.watcher import WorktreeWatcher
from packages.daemon.sync import BlackboardSynchronizer
from packages.daemon.service import MultiWorktreeDaemon

# Export convenient alias
WorktreeDaemon = MultiWorktreeDaemon

__all__ = [
    "WorktreeWatcher",
    "BlackboardSynchronizer",
    "MultiWorktreeDaemon",
    "WorktreeDaemon",
]
