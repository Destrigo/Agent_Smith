import subprocess
from typing import Any, cast
from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve
from shared_tools._docker import is_docker_mode, docker_exec


@mcp.tool()
def run_command(command: str, workdir: str = "/testbed") -> dict[str, Any]:
    """
    Execute a shell command inside the testbed working directory.
    In SWE-bench mode the command runs inside the Docker container.
    Returns stdout, stderr, and exit code.
    """
    if is_docker_mode():
        return cast(dict[str, Any], docker_exec(command, workdir=workdir))

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=_resolve(workdir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"ERROR: {str(e)}",
            "exit_code": -1,
        }
