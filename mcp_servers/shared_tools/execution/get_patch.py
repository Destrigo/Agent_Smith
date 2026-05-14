import subprocess
from mcp_server import mcp_server as mcp

@mcp.tool()
def get_patch() -> str:
    result = subprocess.run(
        ["git", "diff"],
        cwd="/testbed",
        capture_output=True,
        text=True
    )

    return result.stdout