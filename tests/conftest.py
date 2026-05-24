"""
Shared pytest configuration for the agent-smith test suite.

Adds the mcp_servers/ directory to sys.path so that the shared MCP tool
modules (which do `from mcp_server import mcp_server as mcp`) can be
imported without having to launch an actual MCP server process.
"""

import sys
from pathlib import Path

# Allow `from mcp_server import mcp_server as mcp` inside shared_tools modules.
_MCP_SERVERS_PATH = str(Path(__file__).parent.parent / "mcp_servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)
