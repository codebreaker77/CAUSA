from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(request: Request, limit: int = Query(50, ge=1, le=100)):
    return request.app.state.runtime.list_runs(limit)


def report(request, run_id):
    try:
        return request.app.state.runtime.get_run(run_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}")
def get_run(run_id: str, request: Request):
    return report(request, run_id)


@router.get("/{run_id}/dag")
def get_dag(run_id: str, request: Request):
    report(request, run_id)
    storage = request.app.state.runtime.storage
    nodes = storage.get_session_nodes(run_id)
    edges = [edge for node in nodes for edge in storage.get_outgoing_edges(node.id)]
    return {"nodes": [node.model_dump() for node in nodes],
            "edges": [edge.model_dump() for edge in edges]}
