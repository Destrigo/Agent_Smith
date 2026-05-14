from mcp import MCPServer
import shared_tools as t

mcp = MCPServer()


@mcp.tool()
def read_file(filepath: str, start_line: int = 1, end_line: int = 100):
    return t.read_file(filepath, start_line, end_line)


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str):
    return t.edit_file(filepath, old_str, new_str)


@mcp.tool()
def run_command(command: str, workdir: str):
    return t.run_command(command, workdir)


@mcp.tool()
def get_patch():
    return t.run_command("git diff", workdir="/testbed")
