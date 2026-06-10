import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVERS = os.path.join(_ROOT, "mcp_servers")
for _p in (_MCP_SERVERS, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shared_tools.execution.get_patch      # noqa: F401, E402
import shared_tools.execution.run_command    # noqa: F401, E402
import shared_tools.execution.run_tests      # noqa: F401, E402
import shared_tools.filesystem.edit_file     # noqa: F401, E402
import shared_tools.filesystem.list_files    # noqa: F401, E402
import shared_tools.filesystem.read_file     # noqa: F401, E402
import shared_tools.filesystem.write_file    # noqa: F401, E402
import shared_tools.search.find_definition   # noqa: F401, E402
import shared_tools.search.find_references   # noqa: F401, E402
import shared_tools.search.grep_context      # noqa: F401, E402
import shared_tools.search.search_code       # noqa: F401, E402

from mcp_server import mcp_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="SWE-bench MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--port", type=int, default=8001, help="HTTP port")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.settings.host = args.host
        mcp_server.settings.port = args.port
        mcp_server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
