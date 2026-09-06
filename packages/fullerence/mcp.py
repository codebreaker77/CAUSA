"""Agent-facing Model Context Protocol (MCP) server for Fullerence substrate."""

from packages.cli.mcp.server import CausaMCPServer

# Export convenient alias
FullerenceMCPServer = CausaMCPServer

__all__ = [
    "CausaMCPServer",
    "FullerenceMCPServer",
]
