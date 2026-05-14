from mcp_servers.mcp_server import mcp_server
import inspect


def generate_manual():
    lines = []

    for name, tool in mcp_server._tool_manager._tools.items():
        fn = tool.fn

        lines.append(
            f"""
Tool: {name}
Signature: {name}{inspect.signature(fn)}
Description: {fn.__doc__ or "No description"}
"""
        )

    return "\n".join(lines)