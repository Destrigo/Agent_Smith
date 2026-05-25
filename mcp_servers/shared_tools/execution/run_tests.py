import os
import subprocess

from mcp_server import mcp_server as mcp


@mcp.tool()
def run_tests() -> dict:
    """
    Execute the test suite for the current task.

    Behaviour depends on environment variables set by the orchestrator:

    SANDBOX_TEST_CODE   — Python source containing test assertions (MBPP mode).
                          The code is executed with `python -c` inside /testbed.
    SANDBOX_EVAL_SCRIPT — Path to the eval script to run (SWE-bench mode).
                          The script is executed with bash inside /testbed.

    Exactly one of the two variables must be set.  Returns a dict with keys
    stdout, stderr, and exit_code.
    """
    test_code = os.environ.get("SANDBOX_TEST_CODE")
    eval_script = os.environ.get("SANDBOX_EVAL_SCRIPT")

    if test_code:
        result = subprocess.run(
            ["python", "-c", test_code],
            cwd="/testbed",
            capture_output=True,
            text=True,
            timeout=60,
        )
    elif eval_script:
        result = subprocess.run(
            ["bash", eval_script],
            cwd="/testbed",
            capture_output=True,
            text=True,
            timeout=120,
        )
    else:
        return {
            "stdout": "",
            "stderr": (
                "ERROR: neither SANDBOX_TEST_CODE nor SANDBOX_EVAL_SCRIPT "
                "is set.  The orchestrator must configure one of them before "
                "calling run_tests()."
            ),
            "exit_code": -1,
        }

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }
