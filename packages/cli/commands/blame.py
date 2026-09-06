"""Command: fullerenes blame <failedNodeId> - First-Bad-Decision localization."""

from typing import Dict, Any, List
from packages.fullerence.storage import FullerenceStorage
from packages.fullerence.graph import FullerenceGraph
from packages.debugger.localization import localize_first_bad_decision


def format_blame_diagnosis(diagnosis: Dict[str, Any]) -> str:
    """Formats the first-bad-decision diagnostic output."""
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
    """Runs causal root-cause localization and returns formatted diagnostic report."""
    storage = FullerenceStorage(db_path=db_path)
    graph = FullerenceGraph(storage)
    diagnosis = localize_first_bad_decision(storage, graph, failed_node_id)
    return format_blame_diagnosis(diagnosis)
