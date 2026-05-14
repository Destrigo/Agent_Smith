import subprocess

# ALLOWED_DIRS = ["/testbed", "/tmp/agent"]

# def _is_allowed_dir(path: str) -> bool:
#     path = path.rstrip("/")
#     return any(path == d or path.startswith(d + "/") for d in ALLOWED_DIRS)


# @mcp.tool()
def run_command(command: str, workdir: str):
    """
    Execute a shell command inside a restricted working directory.
    Returns stdout, stderr, and exit code.
    """

    # if not _is_allowed_dir(workdir):
    #     return {
    #         "stdout": "",
    #         "stderr": f"ERROR: workdir not allowed: {workdir}",
    #         "exit_code": -1,
    #     }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
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