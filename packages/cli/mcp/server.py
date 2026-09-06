"""Model Context Protocol (MCP) tool server for autonomous coding agents."""

import json
from typing import Dict, Any, List, Optional
from packages.fullerence.storage import FullerenceStorage


class CausaMCPServer:
    """MCP Server exposing causal substrate inspection tools to coding agents."""

    def __init__(self, db_path: str = "graph.db") -> None:
        self.db_path = db_path
        self.storage = FullerenceStorage(db_path=db_path)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns the list of available MCP tools and their parameter schemas."""
        return [
            {
                "name": "get_blackboard_signatures",
                "description": "Query live function, class, and interface signatures exported across peer agent worktrees.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Optional filter by exporting agent ID",
                        }
                    },
                },
            },
            {
                "name": "get_causal_history",
                "description": "Read preceding steps, decisions, and causal events for the current session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Causa session ID to inspect",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of recent nodes to return",
                            "default": 20,
                        },
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "check_file_lease",
                "description": "Check if a file is currently locked/leased by a peer agent to prevent concurrent edit collisions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative repository file path to check",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the requested tool and returns the JSON-serializable result."""
        if tool_name == "get_blackboard_signatures":
            return self._tool_get_blackboard_signatures(arguments.get("agent_id"))
        elif tool_name == "get_causal_history":
            session_id = arguments.get("session_id", "")
            limit = int(arguments.get("limit", 20))
            return self._tool_get_causal_history(session_id, limit)
        elif tool_name == "check_file_lease":
            file_path = arguments.get("file_path", "")
            return self._tool_check_file_lease(file_path)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _tool_get_blackboard_signatures(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        entries = self.storage.get_blackboard()
        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]

        return {
            "count": len(entries),
            "signatures": [
                {
                    "symbol_id": e.symbol_id,
                    "name": e.name,
                    "signature": e.signature,
                    "file_path": e.file_path,
                    "agent_id": e.agent_id,
                    "updated_at": e.updated_at,
                }
                for e in entries
            ],
        }

    def _tool_get_causal_history(self, session_id: str, limit: int = 20) -> Dict[str, Any]:
        nodes = self.storage.get_session_nodes(session_id)
        sliced = nodes[-limit:] if len(nodes) > limit else nodes

        return {
            "session_id": session_id,
            "total_nodes": len(nodes),
            "history": [
                {
                    "node_id": n.id,
                    "agent_id": n.agent_id,
                    "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                    "status": n.status,
                    "tool_name": n.tool_name,
                    "worktree_path": n.worktree_path,
                    "prompt_preview": (n.prompt_snapshot[:80] + "...") if n.prompt_snapshot else None,
                    "created_at": n.created_at,
                }
                for n in sliced
            ],
        }

    def _tool_check_file_lease(self, file_path: str) -> Dict[str, Any]:
        lease = self.storage.get_active_lease(file_path)
        if lease:
            return {
                "file_path": file_path,
                "is_locked": True,
                "held_by_agent": lease.agent_id,
                "lock_state": lease.lock_state.value if hasattr(lease.lock_state, "value") else str(lease.lock_state),
                "timestamp": lease.timestamp,
            }
        return {
            "file_path": file_path,
            "is_locked": False,
            "held_by_agent": None,
            "lock_state": "available",
        }

    def handle_rpc_request(self, request_str: str) -> str:
        """Processes a standard JSON-RPC 2.0 message string and returns response string."""
        try:
            req = json.loads(request_str)
        except Exception as e:
            return json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}, "id": None})

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/list":
            result = {"tools": self.list_tools()}
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                content = self.call_tool(tool_name, arguments)
                result = {"content": [{"type": "text", "text": json.dumps(content, indent=2)}]}
            except Exception as err:
                return json.dumps({"jsonrpc": "2.0", "error": {"code": -32000, "message": str(err)}, "id": req_id})
        else:
            return json.dumps({"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method {method} not found"}, "id": req_id})

        return json.dumps({"jsonrpc": "2.0", "result": result, "id": req_id})
