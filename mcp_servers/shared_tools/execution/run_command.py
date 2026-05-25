import subprocess
from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve


@mcp.tool()
def run_command(command: str, workdir: str):
    """
    Execute a shell command inside a restricted working directory.
    Returns stdout, stderr, and exit code.
    """

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