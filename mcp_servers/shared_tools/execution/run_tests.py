import json
import os
import subprocess
from typing import List, Optional

from mcp_server import mcp_server as mcp


@mcp.tool()
def run_tests(
    code: Optional[str] = None,
    test_list: Optional[List[str]] = None,
) -> str:
    """
    Execute the test suite for the current task.

    MBPP mode (two ways — equivalent):
      1. Pass code + test_list directly:
           run_tests(code="def add(a,b): return a+b", test_list=["assert add(1,2)==3"])
      2. Set SANDBOX_TEST_CODE env var (legacy orchestrator mode).

    SWE-bench mode:
      Set SANDBOX_EVAL_SCRIPT env var to the eval script path.

    Returns a JSON string with keys: success (bool), output (str).
    """
    # --- MBPP inline mode (exam API) ------------------------------------
    if code is not None and test_list is not None:
        combined = code + "\n" + "\n".join(test_list)
        try:
            namespace: dict = {}
            exec(combined, namespace)  # noqa: S102
            return json.dumps({"success": True, "output": "ALL TESTS PASSED"})
        except AssertionError as exc:
            return json.dumps({"success": False,
                               "output": f"ASSERTION FAILED: {exc}"})
        except Exception as exc:
            return json.dumps({"success": False,
                               "output": f"{type(exc).__name__}: {exc}"})

    # --- Legacy env-var mode -------------------------------------------
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
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return json.dumps({"success": success,
                           "output": output or "ALL TESTS PASSED" if success else output,
                           "stdout": result.stdout,
                           "stderr": result.stderr,
                           "exit_code": result.returncode})

    elif eval_script:
        result = subprocess.run(
            ["bash", eval_script],
            cwd="/testbed",
            capture_output=True,
            text=True,
            timeout=120,
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return json.dumps({"success": success,
                           "output": output,
                           "stdout": result.stdout,
                           "stderr": result.stderr,
                           "exit_code": result.returncode})

    else:
        return json.dumps({
            "success": False,
            "output": (
                "ERROR: neither SANDBOX_TEST_CODE nor SANDBOX_EVAL_SCRIPT "
                "is set, and no code/test_list arguments were provided."
            ),
            "exit_code": -1,
        })
