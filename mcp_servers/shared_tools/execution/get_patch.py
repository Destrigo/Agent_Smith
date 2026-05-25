import subprocess

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed


@mcp.tool()
def get_patch() -> str:
    """Return the unified diff of all changes made inside /testbed."""
    result = subprocess.run(
        ["git", "-c", "core.fileMode=false", "diff"],
        cwd=testbed(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"(no changes or git error: {result.stderr.strip()})"
    return result.stdout
