import subprocess

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed
from shared_tools._docker import is_docker_mode, docker_exec


@mcp.tool()
def get_patch() -> str:
    """Return the unified diff of all changes made inside /testbed."""
    if is_docker_mode():
        result = docker_exec(
            "git -c core.fileMode=false diff",
            workdir="/testbed",
        )
        if result["exit_code"] != 0:
            return f"(no changes or git error: {result['stderr'].strip()})"
        return str(result["stdout"])

    result = subprocess.run(
        ["git", "-c", "core.fileMode=false", "diff"],
        cwd=testbed(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"(no changes or git error: {result.stderr.strip()})"
    return str(result.stdout)
