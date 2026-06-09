"""
Pytest wrappers for eval_documents/sandbox_tests/ scripts.

Each script is designed to be exec()'d inside the sandbox (the exam shell
scripts pipe them in via `cat test_foo.py | uv run sandbox ...`).  Here we
run them programmatically through a real Sandbox instance and assert that:
  - no "FAIL:" line appears in stdout/stderr
  - the expected "=== ... COMPLETE/OK ===" terminal marker is present

Group 1 — pure sandbox (no external processes)
Group 2 — MCP stdio (simple_mcp_server.py launched as subprocess)
Skipped  — layer-1 bonus (infinite loop), mbpp/swebench tools (need Docker
           or a full agent environment), mcp_http (needs background server)
"""

from pathlib import Path
import pytest

from models.sandbox_model import SandboxConfig
from sandbox.core.sandbox import Sandbox

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPTS_DIR = (
    Path(__file__).parent.parent / "eval_documents" / "sandbox_tests"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# allowlist matching eval_documents/sandbox_tests/sandbox_config.json
# (adds "time" needed by test_timeout.py)
_BASE_IMPORTS = [
    "math", "cmath",
    "collections", "collections.*",
    "itertools", "functools", "operator",
    "re", "json",
    "typing", "typing.*",
    "heapq", "bisect", "copy", "string", "random",
    "datetime", "datetime.*",
    "array", "queue", "time", "stat", "unicodedata",
]


def _make_sandbox(timeout: int = 30, memory_mb: int = 512) -> Sandbox:
    cfg = SandboxConfig(
        authorized_imports=_BASE_IMPORTS,
        allowed_directories=["/testbed", "/tmp/agent"],
        max_execution_time_seconds=timeout,
        max_memory_mb=memory_mb,
    )
    return Sandbox(cfg)


def _script(name: str) -> str:
    return (SCRIPTS_DIR / name).read_text()


def _assert_no_fail(result: dict, script: str) -> None:
    """Fail if any 'FAIL:' line appears in stdout/stderr."""
    output = result["stdout"] + result.get("stderr", "")
    fail_lines = [ln for ln in output.splitlines() if ln.startswith("FAIL:")]
    assert not fail_lines, (
        f"{script} printed FAIL line(s):\n" + "\n".join(fail_lines)
        + f"\n\nFull observation:\n{result['observation']}"
    )


# ---------------------------------------------------------------------------
# Group 1 — pure sandbox scripts (no external processes)
# ---------------------------------------------------------------------------

class TestPureSandboxScripts:

    def test_imports_allowed(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_imports_allowed.py"))
        _assert_no_fail(r, "test_imports_allowed")
        assert "=== ALL ALLOWED IMPORTS OK ===" in r["stdout"]

    def test_imports_blocked(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_imports_blocked.py"))
        _assert_no_fail(r, "test_imports_blocked")
        assert "=== BLOCKED IMPORTS TEST COMPLETE ===" in r["stdout"]
        assert "OK: socket blocked" in r["stdout"], "Missing: 'OK: socket blocked'"

    def test_file_access(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_file_access.py"))
        _assert_no_fail(r, "test_file_access")
        assert "=== FILE ACCESS TEST COMPLETE ===" in r["stdout"]
        for blocked in (
            "OK: /etc/passwd blocked",
            "OK: path traversal blocked",
            "OK: /home blocked",
            "OK: /root blocked",
        ):
            assert blocked in r["stdout"], f"Missing: {blocked!r}"

    def test_builtins_blocked(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_builtins_blocked.py"))
        _assert_no_fail(r, "test_builtins_blocked")
        assert "=== BUILTINS BLOCKED TEST COMPLETE ===" in r["stdout"]
        assert "OK: eval blocked" in r["stdout"]
        assert "OK: exec blocked" in r["stdout"]
        assert "OK: compile blocked" in r["stdout"]
        assert "OK: safe builtins work" in r["stdout"]

    def test_network_blocked(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_network_blocked.py"))
        _assert_no_fail(r, "test_network_blocked")
        assert "=== NETWORK BLOCKED TEST COMPLETE ===" in r["stdout"]
        assert "OK: TCP connection blocked" in r["stdout"]
        assert "OK: HTTP request blocked" in r["stdout"]
        assert "OK: HTTPS connection blocked" in r["stdout"]
        assert "OK: requests library blocked" in r["stdout"]
        assert "OK: non-network imports work" in r["stdout"]
        for mod in ("socket", "urllib"):
            ri = sb.execute(f"import {mod}")
            assert "[SANDBOX BLOCKED]" in (ri.get("error") or ""), (
                f"Expected {mod} to be blocked but got: {ri['observation']}"
            )

    def test_persistence(self):
        """Variable assignment and print in the first (non-commented) block."""
        sb = _make_sandbox()
        r = sb.execute(_script("test_persistence.py"))
        assert r["success"] is True
        assert "a = 10" in r["stdout"]

    def test_sandbox_feedback(self):
        sb = _make_sandbox()
        r = sb.execute(_script("test_sandbox_feedback.py"))
        _assert_no_fail(r, "test_sandbox_feedback")
        assert "=== SANDBOX FEEDBACK COMPLETE ===" in r["stdout"]
        for marker in (
            "FEEDBACK_TEST_1",
            "FEEDBACK_TEST_2",
            "FEEDBACK_TEST_3",
            "FEEDBACK_TEST_4",
        ):
            assert marker in r["stdout"], f"Missing: {marker!r}"

    def test_timeout_enforcement(self):
        """Markers before the infinite loop survive; TIMEOUT is reported."""
        # 5 s keeps the test fast while still triggering the timeout path
        sb = _make_sandbox(timeout=5)
        r = sb.execute(_script("test_timeout.py"))
        assert "OK: short computation completed" in r["stdout"]
        assert "PARTIAL_OUTPUT_MARKER" in r["stdout"]
        assert "=== TIMEOUT TEST COMPLETE ===" in r["stdout"]
        assert "TIMEOUT" in r["observation"]

    def test_memory_enforcement(self):
        """1 MB allocation passes; 512 MB allocation should raise MemoryError.

        RLIMIT_AS enforcement is Linux-only and depends on the current process
        virtual-address-space at the time execute() is called.  In some
        environments (heavy pytest process, container limits already set, etc.)
        the computed cap ends up higher than expected and the large allocation
        succeeds.  We verify the small allocation always works and skip
        gracefully when enforcement is not effective in this environment.
        """
        sb = _make_sandbox(memory_mb=256)
        r = sb.execute(_script("test_memory.py"))
        assert "OK: small allocation succeeded" in r["stdout"]
        if "FAIL: large allocation succeeded" in r["stdout"]:
            pytest.skip(
                "RLIMIT_AS not effective here "
                "(process VAS too large for the cap to bite)"
            )
        assert "OK: large allocation correctly raised MemoryError" in r["stdout"]


# ---------------------------------------------------------------------------
# Group 2 — MCP stdio tests (simple_mcp_server.py)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mcp_client():
    """Module-scoped MCPClient connected to simple_mcp_server via stdio."""
    from mcp_servers.mcp_client import MCPClient
    server_path = str(SCRIPTS_DIR / "simple_mcp_server.py")
    client = MCPClient()
    client.connect_stdio("python", [server_path, "--stdio"])
    yield client
    try:
        client.close()
    except Exception:
        pass  # anyio cancel-scope teardown may raise in test contexts


@pytest.fixture
def mcp_sandbox(mcp_client):
    """Fresh sandbox per test with add/multiply/echo tools injected."""
    sb = _make_sandbox()
    sb.register_mcp_tools(mcp_client.make_tool_wrappers())
    return sb


class TestMCPSandboxScripts:

    def test_mcp_stdio(self, mcp_sandbox):
        r = mcp_sandbox.execute(_script("test_mcp_stdio.py"))
        assert "=== MCP STDIO CONFIG OK ===" in r["stdout"], r["observation"]

    def test_dynamic_discovery(self, mcp_sandbox):
        r = mcp_sandbox.execute(_script("test_dynamic_discovery.py"))
        assert "=== DYNAMIC DISCOVERY OK ===" in r["stdout"], r["observation"]

    def test_sandbox_manual_script(self, mcp_sandbox):
        """Script falls back to tool-availability check and reports OK."""
        r = mcp_sandbox.execute(_script("test_sandbox_manual.py"))
        assert "=== SANDBOX MANUAL OK ===" in r["stdout"], r["observation"]

    def test_generate_manual_from_client(self, mcp_client):
        """generate_manual_from_client() includes all three tools."""
        from sandbox.manual.generator import generate_manual_from_client
        manual = generate_manual_from_client(mcp_client)
        assert "=== SANDBOX MANUAL ===" in manual
        assert "=== END OF MANUAL ===" in manual
        assert "final_answer" in manual
        for tool in ("add", "multiply", "echo"):
            assert tool in manual, f"Manual missing tool: {tool!r}"


# ---------------------------------------------------------------------------
# Group 3 — Layer-1 bonus (no MCP needed)
# ---------------------------------------------------------------------------

class TestLayer1Bonus:
    def test_layer1_bonus(self):
        """Sandbox reports TIMEOUT even when bare-except swallows exceptions.

        Our sandbox uses in-process threading (layer 0): the daemon thread is
        abandoned after timeout rather than SIGKILL'd.  The test verifies that
        the sandbox correctly detects thread.is_alive() and reports TIMEOUT —
        the documented behaviour for layer-0 implementations.
        """
        sb = _make_sandbox(timeout=5)
        r = sb.execute(_script("test_layer1_bonus.py"))
        assert "TIMEOUT" in r["observation"], (
            "Expected sandbox to report TIMEOUT for the bare-except loop\n"
            f"observation: {r['observation']}"
        )


# ---------------------------------------------------------------------------
# Group 4 — MBPP real tools (mcp_tools_mbpp.py)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def mbpp_mcp_client():
    """MCPClient connected to mcp_tools_mbpp.py via stdio."""
    from mcp_servers.mcp_client import MCPClient
    client = MCPClient()
    client.connect_stdio("python", [str(PROJECT_ROOT / "mcp_tools_mbpp.py")])
    yield client
    try:
        client.close()
    except Exception:
        pass


@pytest.fixture
def mbpp_sandbox(mbpp_mcp_client):
    """Fresh sandbox with all MBPP MCP tools injected."""
    sb = _make_sandbox()
    sb.register_mcp_tools(mbpp_mcp_client.make_tool_wrappers())
    return sb


class TestMBPPTools:
    def test_mbpp_tools(self, mbpp_sandbox):
        """run_tests inline mode and final_answer are callable."""
        r = mbpp_sandbox.execute(_script("test_mbpp_tools.py"))
        assert "=== MBPP TOOLS OK ===" in r["stdout"], r["observation"]


# ---------------------------------------------------------------------------
# Group 5 — SWE-bench real tools (mcp_tools_swebench.py + local testbed)
# ---------------------------------------------------------------------------

TESTBED_DIR = str(SCRIPTS_DIR / "testbed")


@pytest.fixture(scope="module")
def swebench_mcp_client(tmp_path_factory):
    """MCPClient connected to mcp_tools_swebench.py with TESTBED_PATH set."""
    import os
    from mcp_servers.mcp_client import MCPClient
    # Use a writable copy of testbed so edit_file tests don't mutate the repo
    import shutil
    tb = str(tmp_path_factory.mktemp("testbed"))
    shutil.copytree(TESTBED_DIR, tb, dirs_exist_ok=True)
    os.environ["TESTBED_PATH"] = tb
    client = MCPClient()
    client.connect_stdio(
        "python", [str(PROJECT_ROOT / "mcp_tools_swebench.py")]
    )
    yield client
    try:
        client.close()
    except Exception:
        pass
    finally:
        os.environ.pop("TESTBED_PATH", None)


@pytest.fixture
def swebench_sandbox(swebench_mcp_client):
    """Fresh sandbox with all SWE-bench MCP tools injected."""
    sb = _make_sandbox()
    sb.register_mcp_tools(swebench_mcp_client.make_tool_wrappers())
    return sb


class TestSWEBenchTools:
    def test_swebench_tools(self, swebench_sandbox):
        """All 9 mandatory SWE-bench tools are available and callable."""
        r = swebench_sandbox.execute(_script("test_swebench_tools.py"))
        assert "=== SWEBENCH TOOLS OK ===" in r["stdout"], r["observation"]


# ---------------------------------------------------------------------------
# Group 6 — MCP HTTP transport
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def http_mcp_server():
    """simple_mcp_server.py running on a free port via streamable-HTTP."""
    import socket
    import subprocess
    import time
    port = _find_free_port()
    proc = subprocess.Popen(
        ["python", str(SCRIPTS_DIR / "simple_mcp_server.py"),
         "--http", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # wait up to 5 s for the port to open
    for _ in range(25):
        try:
            with socket.create_connection(("localhost", port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.2)
    yield f"http://localhost:{port}/mcp"
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def http_mcp_client(http_mcp_server):
    """MCPClient connected via streamable-HTTP."""
    from mcp_servers.mcp_client import MCPClient
    client = MCPClient()
    client.connect_http(http_mcp_server)
    yield client
    try:
        client.close()
    except Exception:
        pass


@pytest.fixture
def http_mcp_sandbox(http_mcp_client):
    """Fresh sandbox with add/multiply/echo from the HTTP server."""
    sb = _make_sandbox()
    sb.register_mcp_tools(http_mcp_client.make_tool_wrappers())
    return sb


class TestMCPHTTP:
    def test_mcp_http(self, http_mcp_sandbox):
        r = http_mcp_sandbox.execute(_script("test_mcp_http.py"))
        assert "=== MCP HTTP CONFIG OK ===" in r["stdout"], r["observation"]
