"""
Tests for sandbox/core/sandbox.py

Covers: normal execution, final_answer signal, syntax errors,
blocked modules, blocked builtins, restricted file access,
allowed imports, timeout, output capture, truncation,
MCP tool injection, and the static feedback helpers.
"""

import pytest
from models.sandbox_model import SandboxConfig
from sandbox.core.sandbox import Sandbox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sandbox(**kwargs) -> Sandbox:
    """Return a Sandbox with a SandboxConfig, overridable via kwargs."""
    config = SandboxConfig(**kwargs)
    return Sandbox(config)


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

class TestBasicExecution:
    def test_simple_print(self):
        sb = make_sandbox()
        result = sb.execute("print('hello')")
        assert result["success"] is True
        assert "hello" in result["stdout"]
        assert result["error"] is None
        assert result["final_answer"] is None

    def test_arithmetic(self):
        sb = make_sandbox()
        result = sb.execute("x = 2 + 2\nprint(x)")
        assert result["success"] is True
        assert "4" in result["stdout"]

    def test_no_output_is_still_success(self):
        sb = make_sandbox()
        result = sb.execute("x = 1 + 1")
        assert result["success"] is True
        assert result["stdout"] == ""
        assert result["error"] is None

    def test_observation_contains_stdout(self):
        sb = make_sandbox()
        result = sb.execute("print('sentinel_value')")
        assert "sentinel_value" in result["observation"]

    def test_stderr_captured(self):
        # `sys` is in the blocked-modules list so it cannot be imported from
        # within the sandbox. Inject it directly into the namespace instead —
        # this also exercises the namespace-injection path used by MCP tools.
        import sys as real_sys
        sb = make_sandbox()
        sb._namespace["sys"] = real_sys
        result = sb.execute("print('err', file=sys.stderr)")
        assert "err" in result["stderr"]
        assert "[stderr]" in result["observation"]

    def test_namespace_persists_across_calls(self):
        """Variables defined in one execute() are visible in the next."""
        sb = make_sandbox()
        sb.execute("counter = 10")
        result = sb.execute("print(counter)")
        assert "10" in result["stdout"]


# ---------------------------------------------------------------------------
# final_answer signal
# ---------------------------------------------------------------------------

class TestFinalAnswer:
    def test_final_answer_sets_field(self):
        sb = make_sandbox()
        result = sb.execute("final_answer('42')")
        assert result["final_answer"] == "42"
        assert result["success"] is True

    def test_final_answer_in_observation(self):
        sb = make_sandbox()
        result = sb.execute("final_answer('done')")
        assert "final_answer submitted" in result["observation"]
        assert "done" in result["observation"]

    def test_final_answer_stops_execution(self):
        """Code after final_answer() should not run (FinalAnswerSignal)."""
        sb = make_sandbox()
        result = sb.execute(
            "final_answer('stop')\nprint('should_not_appear')"
        )
        assert "should_not_appear" not in result["stdout"]
        assert result["final_answer"] == "stop"


# ---------------------------------------------------------------------------
# Syntax errors
# ---------------------------------------------------------------------------

class TestSyntaxErrors:
    def test_syntax_error_caught(self):
        sb = make_sandbox()
        result = sb.execute("def foo(:\n    pass")
        assert result["success"] is False
        assert "SyntaxError" in result["error"]
        assert "[SANDBOX ERROR]" in result["error"]

    def test_syntax_error_observation(self):
        sb = make_sandbox()
        result = sb.execute("!!!invalid code!!!")
        assert result["success"] is False
        assert "SyntaxError" in result["observation"]


# ---------------------------------------------------------------------------
# Blocked modules
# ---------------------------------------------------------------------------

class TestBlockedModules:
    @pytest.mark.parametrize("module", [
        "os", "sys", "subprocess", "socket", "urllib",
        "threading", "asyncio", "pickle", "shutil",
    ])
    def test_blocked_module_raises(self, module):
        sb = make_sandbox()
        result = sb.execute(f"import {module}")
        assert result["success"] is False
        assert "[SANDBOX BLOCKED]" in result["error"]

    def test_blocked_via_from_import(self):
        sb = make_sandbox()
        result = sb.execute("from os import path")
        assert result["success"] is False
        assert "[SANDBOX BLOCKED]" in result["error"]

    def test_not_in_allowlist_raises(self):
        sb = make_sandbox()
        result = sb.execute("import numpy")
        assert result["success"] is False
        # "numpy" is neither blocked nor in the default authorised_imports list
        assert "[SANDBOX BLOCKED]" in result["error"]


# ---------------------------------------------------------------------------
# Blocked builtins
# ---------------------------------------------------------------------------

class TestBlockedBuiltins:
    def test_eval_is_blocked(self):
        sb = make_sandbox()
        result = sb.execute("eval('1+1')")
        assert result["success"] is False
        assert "NameError" in result["error"]

    def test_exec_is_blocked(self):
        sb = make_sandbox()
        result = sb.execute("exec('x=1')")
        assert result["success"] is False
        assert "NameError" in result["error"]

    def test_compile_is_blocked(self):
        sb = make_sandbox()
        result = sb.execute("compile('1+1', '<s>', 'eval')")
        assert result["success"] is False
        assert "NameError" in result["error"]


# ---------------------------------------------------------------------------
# Restricted open / file access
# ---------------------------------------------------------------------------

class TestRestrictedFileAccess:
    def test_open_blocked_outside_allowed_dirs(self, tmp_path):
        # tmp_path is outside /testbed and /tmp/agent so it must be blocked
        target = tmp_path / "secret.txt"
        target.write_text("secret")
        sb = make_sandbox()
        result = sb.execute(f"open(r'{target}', 'r')")
        assert result["success"] is False
        assert "[SANDBOX BLOCKED]" in result["error"]

    def test_open_allowed_inside_permitted_dir(self, tmp_path):
        # Use a custom SandboxConfig that permits tmp_path
        target = tmp_path / "data.txt"
        target.write_text("hello\n")
        sb = Sandbox(
            SandboxConfig(allowed_directories=[str(tmp_path)])
        )
        result = sb.execute(
            f"f = open(r'{target}'); print(f.read()); f.close()"
        )
        assert result["success"] is True
        assert "hello" in result["stdout"]


# ---------------------------------------------------------------------------
# Allowed imports
# ---------------------------------------------------------------------------

class TestAllowedImports:
    @pytest.mark.parametrize("module,code", [
        ("math", "import math; print(math.pi)"),
        ("collections", "from collections import defaultdict; print('ok')"),
        ("json", "import json; print(json.dumps({'a': 1}))"),
        ("re", "import re; print(re.match(r'\\d+', '42').group())"),
        ("itertools", "import itertools; print(list(itertools.islice(itertools.count(), 3)))"),
    ])
    def test_allowed_import(self, module, code):
        sb = make_sandbox()
        result = sb.execute(code)
        assert result["success"] is True, f"Expected {module} to be importable, got: {result['error']}"

    def test_custom_authorized_imports(self):
        sb = Sandbox(SandboxConfig(authorized_imports=["math"]))
        # math is allowed
        assert sb.execute("import math")["success"] is True
        # json is not in the custom list
        result = sb.execute("import json")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_timeout_returns_error(self):
        sb = Sandbox(SandboxConfig(max_execution_time_seconds=1))
        result = sb.execute("while True: pass")
        assert result["success"] is False
        assert "[SANDBOX TIMEOUT]" in result["error"]
        assert "[SANDBOX TIMEOUT]" in result["observation"]


# ---------------------------------------------------------------------------
# Runtime exceptions (not SyntaxError)
# ---------------------------------------------------------------------------

class TestRuntimeExceptions:
    def test_zerodivision(self):
        sb = make_sandbox()
        result = sb.execute("1 / 0")
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    def test_name_error(self):
        sb = make_sandbox()
        result = sb.execute("print(undefined_variable)")
        assert result["success"] is False
        assert "NameError" in result["error"]

    def test_error_in_observation(self):
        sb = make_sandbox()
        result = sb.execute("raise ValueError('bad input')")
        assert "ValueError" in result["observation"]
        assert "bad input" in result["observation"]


# ---------------------------------------------------------------------------
# MCP tool injection
# ---------------------------------------------------------------------------

class TestMCPToolInjection:
    def test_injected_tool_callable(self):
        sb = make_sandbox()
        calls = []

        def my_tool(value):
            calls.append(value)
            return value * 2

        sb.register_mcp_tools({"my_tool": my_tool})
        result = sb.execute("x = my_tool(21)\nprint(x)")
        assert result["success"] is True
        assert "42" in result["stdout"]
        assert calls == [21]

    def test_multiple_tools_injected(self):
        sb = make_sandbox()
        sb.register_mcp_tools({
            "add": lambda a, b: a + b,
            "mul": lambda a, b: a * b,
        })
        result = sb.execute("print(add(3, 4) + mul(2, 5))")
        assert result["success"] is True
        assert "17" in result["stdout"]


# ---------------------------------------------------------------------------
# Static feedback helpers
# ---------------------------------------------------------------------------

class TestStaticHelpers:
    def test_no_code_feedback_structure(self):
        fb = Sandbox.no_code_feedback()
        assert fb["success"] is False
        assert fb["final_answer"] is None
        assert fb["truncated"] is False
        assert "[SANDBOX ERROR]" in fb["observation"]
        assert "code block" in fb["observation"]

    def test_malformed_code_feedback_is_string(self):
        msg = Sandbox.malformed_code_feedback(
            original="```py\nx = 1",
            interpreted="x = 1",
        )
        assert isinstance(msg, str)
        assert "[SANDBOX WARNING]" in msg
        assert "x = 1" in msg


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------

class TestOutputTruncation:
    def test_large_output_is_truncated(self):
        # Write more than 8192 bytes to stdout
        sb = make_sandbox()
        result = sb.execute("print('x' * 9000)")
        assert result["truncated"] is True
        assert "[SANDBOX TRUNCATED]" in result["error"]
        # Despite truncation, the call itself may still be marked success
        # (sandbox ran without exception), and stdout should be non-empty
        assert len(result["stdout"]) > 0
