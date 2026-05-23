"""
MCP server for MBPP benchmark tasks.

Exposes all shared tools plus the MBPP-specific run_tests tool.

Usage
-----
    # stdio (used when the sandbox launches this as a subprocess)
    python mcp_tools_mbpp.py

    # streamable HTTP
    python mcp_tools_mbpp.py --transport http --host 0.0.0.0 --port 8000
"""

import argparse
import os
import sys

# When run as a subprocess, ensure the mcp_servers/ directory is on sys.path
# so that `import shared_tools.*` and `import mcp_server` resolve correctly.
sys.path.insert(0, os.path.dirname(__file__))

# Importing these modules registers their tools with the shared mcp_server
# instance via the @mcp.tool() decorator.
import shared_tools.execution.get_patch      # noqa: F401
import shared_tools.execution.run_command    # noqa: F401
import shared_tools.execution.run_tests      # noqa: F401
import shared_tools.filesystem.edit_file     # noqa: F401
import shared_tools.filesystem.list_files    # noqa: F401
import shared_tools.filesystem.read_file     # noqa: F401
import shared_tools.search.find_definition   # noqa: F401
import shared_tools.search.find_references   # noqa: F401
import shared_tools.search.search_code       # noqa: F401

from mcp_server import mcp_server


def main() -> None:
    parser = argparse.ArgumentParser(description="MBPP MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
