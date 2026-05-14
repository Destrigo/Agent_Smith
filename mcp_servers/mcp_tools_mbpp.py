from mcp import MCPServer
import shared_tools as t

mcp = MCPServer()


@mcp.tool()
def run_tests():
    """Run MBPP tests."""
    return t.run_command("pytest", workdir="/testbed")
