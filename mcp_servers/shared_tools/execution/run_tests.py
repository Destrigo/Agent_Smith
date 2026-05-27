import os
import subprocess
from typing import List, Optional

from mcp_server import mcp_server as mcp


@mcp.tool()
def run_tests(
    code: Optional[str] = None,
    test_list: Optional[List[str]] = None,
) -> dict:
    """
    Execute the test suite for the current task.

    MBPP inline mode (exam API):
      run_tests(code="def add(a,b): return a+b", test_list=["assert add(1,2)==3"])
      Returns: {"success": bool, "output": str, "stdout": str, "stderr": str, "exit_code": int}

    Legacy env-var mode (orchestrator sets env before spawning MCP server):
      SANDBOX_TEST_CODE  — Python source with assertions (MBPP)
      SANDBOX_EVAL_SCRIPT — Path to bash eval script (SWE-bench)

    NOTE: when called via MCP the dict is serialised to a JSON text string by
    the MCP framework.  Callers that receive it through the MCP client should
    use json.loads() on the returned string.
    """
    # --- MBPP inline mode (exam API) ------------------------------------
    if code is not None and test_list is not None:
        combined = code + "\n" + "\n".join(test_list)
        try:
            # Restrict builtins to prevent the agent from importing arbitrary
            # modules or accessing dangerous builtins through this code path.
            _blocked = {"eval", "exec", "compile", "__import__", "open",
                        "input", "breakpoint"}
            import builtins as _bi
            safe_builtins = {k: v for k, v in vars(_bi).items()
                             if k not in _blocked}
            namespace: dict = {"__builtins__": safe_builtins}
            exec(combined, namespace)  # noqa: S102
            return {"success": True, "output": "ALL TESTS PASSED",
                    "stdout": "", "stderr": "", "exit_code": 0}
        except AssertionError as exc:
            msg = f"ASSERTION FAILED: {exc}"
            return {"success": False, "output": msg,
                    "stdout": "", "stderr": msg, "exit_code": 1}
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            return {"success": False, "output": msg,
                    "stdout": "", "stderr": msg, "exit_code": 1}

    # --- Legacy env-var mode -------------------------------------------
    test_code = os.environ.get("SANDBOX_TEST_CODE")
    eval_script = os.environ.get("SANDBOX_EVAL_SCRIPT")

    if test_code:
        result = subprocess.run(
            ["python", "-c", test_code],
            cwd=os.environ.get("TESTBED_PATH", "/testbed"),
            capture_output=True,
            text=True,
            timeout=60,
        )
        success = result.returncode == 0
        return {"success": success,
                "output": result.stdout + result.stderr,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode}

    elif eval_script:
        result = subprocess.run(
            ["bash", eval_script],
            cwd=os.environ.get("TESTBED_PATH", "/testbed"),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {"success": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode}

    else:
        msg = ("ERROR: neither SANDBOX_TEST_CODE nor SANDBOX_EVAL_SCRIPT "
               "is set, and no code/test_list arguments were provided.")
        return {"success": False, "output": msg,
                "stdout": "", "stderr": msg, "exit_code": -1}
