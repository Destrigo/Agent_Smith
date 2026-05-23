import subprocess

from mcp_server import mcp_server as mcp


@mcp.tool()
def get_patch() -> str:
    """Return the unified diff of all changes made inside /testbed."""
    result = subprocess.run(
        ["git", "-c", "core.fileMode=false", "diff"],
        cwd="/testbed",
        capture_output=True,
        text=True,
    )
    return result.stdout
