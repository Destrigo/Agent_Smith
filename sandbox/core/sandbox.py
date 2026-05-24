import ast
import builtins as _builtins
import io
import os
import threading
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, List, Optional

from models.sandbox_model import SandboxConfig


class FinalAnswerSignal(BaseException):
    """Raised inside the sandbox when final_answer() is called."""

    def __init__(self, answer: str):
        self.answer = answer


# Modules that must never be importable regardless of the allowlist.
_BLOCKED_MODULES: frozenset = frozenset({
    "os",
    "sys",
    "subprocess",
    "socket",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "ssl",
    "shutil",
    "importlib",
    "ctypes",
    "cffi",
    "multiprocessing",
    "threading",
    "concurrent",
    "asyncio",
    "pickle",
    "shelve",
    "marshal",
    "tempfile",
    "signal",
    "resource",
    "pty",
    "rlcompleter",
    "code",
    "codeop",
    "readline",
    "_thread",
    "gc",
    "weakref",
    "builtins",
})

# Builtins that are always removed from the sandbox namespace.
_BLOCKED_BUILTINS: frozenset = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "__loader__",
    "__spec__",
    "__build_class__",
    "breakpoint",
})

# Maximum bytes captured from stdout + stderr before truncation.
_MAX_OUTPUT_BYTES: int = 8192


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    """Return (possibly-truncated text, was_truncated)."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="replace"), True


class Sandbox:
    """
    Executes LLM-generated Python code in an isolated namespace.

    Security constraints
    --------------------
    - Only modules listed in SandboxConfig.authorized_imports may be imported.
    - File-system access is limited to SandboxConfig.allowed_directories.
    - Network access is blocked (socket and friends are in _BLOCKED_MODULES).
    - Execution is time-limited to SandboxConfig.max_execution_time_seconds.
    - Dangerous builtins (eval, exec, compile, open, …) are removed.

    Feedback contract
    -----------------
    The dict returned by execute() always contains an 'observation' key with a
    human-readable string ready to be appended to the LLM conversation. The LLM
    is never left guessing about what happened:
      - No code block found        → caller sets code="" and checks observation
      - Malformed / interpreted    → caller sets code=cleaned and passes note
      - Timeout                    → observation says "TIMEOUT" + partial output
      - Output truncated           → observation says "TRUNCATED"
      - Normal error               → observation contains the exception text
      - Success                    → observation contains stdout/stderr output

    Design decision — in-process threading
    ---------------------------------------
    We execute code in a daemon thread rather than a subprocess so that the
    sandbox namespace persists across steps. The thread is joined with a
    timeout; if it is still alive after the deadline the result is marked as
    timed-out. True process isolation would require serialising the namespace.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._namespace: Dict[str, Any] = {}
        self._setup_namespace()

    def _setup_namespace(self) -> None:
        self._namespace = {
            "__builtins__": self._make_safe_builtins(),
            "final_answer": self._final_answer_fn,
        }

    def register_mcp_tools(self, tools: Dict[str, Any]) -> None:
        """Inject MCP tool callables into the sandbox namespace."""
        for name, fn in tools.items():
            self._namespace[name] = fn

    def _final_answer_fn(self, answer: str) -> None:
        raise FinalAnswerSignal(str(answer))

    def _make_safe_builtins(self) -> dict:
        safe = {
            k: v for k, v in vars(_builtins).items()
            if k not in _BLOCKED_BUILTINS
        }
        safe["__import__"] = self._restricted_import
        safe["open"] = self._restricted_open
        return safe

    def _is_import_allowed(self, name: str) -> bool:
        base = name.split(".")[0]
        for pattern in self.config.authorized_imports:
            if pattern == name or pattern == base:
                return True
            if pattern.endswith(".*") and pattern[:-2] == base:
                return True
        return False

    def _restricted_import(
        self,
        name: str,
        globals: Optional[dict] = None,
        locals: Optional[dict] = None,
        fromlist: tuple = (),
        level: int = 0,
    ):
        base = name.split(".")[0]
        if base in _BLOCKED_MODULES:
            raise ImportError(
                f"[SANDBOX BLOCKED] Import of '{name}' is blocked "
                f"(module is on the deny list)."
            )
        if not self._is_import_allowed(name):
            raise ImportError(
                f"[SANDBOX BLOCKED] Import of '{name}' is not allowed. "
                f"Authorized imports: "
                f"{self.config.authorized_imports}"
            )
        return _builtins.__import__(name, globals, locals, fromlist, level)

    def _restricted_open(self, path, mode="r", *args, **kwargs):
        abs_path = os.path.realpath(str(path))
        for allowed in self.config.allowed_directories:
            allowed_real = os.path.realpath(allowed)
            if abs_path == allowed_real or abs_path.startswith(
                allowed_real + os.sep
            ):
                return _builtins.open(path, mode, *args, **kwargs)
        raise PermissionError(
            f"[SANDBOX BLOCKED] File access to '{path}' is not allowed. "
            f"Allowed directories: "
            f"{self.config.allowed_directories}"
        )

    # ------------------------------------------------------------------
    # Public helpers for the agent loop — explicit feedback construction
    # ------------------------------------------------------------------

    @staticmethod
    def no_code_feedback() -> dict:
        """
        Return the observation dict when the LLM response had no code block.
        The agent loop should call this instead of execute() and feed the
        result back to the LLM so it knows it must emit a code block.
        """
        msg = (
            "[SANDBOX ERROR] No valid Python code block was found in your "
            "response. You must wrap your code in a markdown code block:\n"
            "```python\n"
            "# your code here\n"
            "```\n"
            "Please try again."
        )
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": msg,
            "final_answer": None,
            "truncated": False,
            "observation": msg,
        }

    @staticmethod
    def malformed_code_feedback(original: str, interpreted: str) -> str:
        """
        Return a warning string when a code block was malformed but the
        agent loop was able to recover and interpret it anyway.
        Callers should still execute `interpreted`; prepend this warning
        to the real execution observation so the LLM knows what happened.
        """
        return (
            f"[SANDBOX WARNING] The code block was malformed. "
            f"It was interpreted as:\n```python\n{interpreted}\n```\n"
            f"Original response snippet:\n{original[:200]}"
        )

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(self, code: str) -> dict:
        """
        Execute *code* inside the sandbox.

        Returns a dict with keys:
            success      bool
            stdout       str   (possibly truncated)
            stderr       str   (possibly truncated)
            error        str | None  — exception / timeout / truncation note
            final_answer str | None  — value passed to final_answer(), if any
            truncated    bool  — True when stdout/stderr were cut
            observation  str   — ready-to-use feedback string for the LLM
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            msg = f"[SANDBOX ERROR] SyntaxError: {e}"
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": msg,
                "final_answer": None,
                "truncated": False,
                "observation": msg,
            }

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        outcome: Dict[str, Any] = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": None,
            "final_answer": None,
            "truncated": False,
            "observation": "",
        }
        exc_holder: List[BaseException] = []
        fa_holder: List[str] = []

        def _run() -> None:
            try:
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    exec(code, self._namespace)  # noqa: S102
                outcome["success"] = True
            except FinalAnswerSignal as fa:
                outcome["success"] = True
                fa_holder.append(fa.answer)
            except (KeyboardInterrupt, SystemExit):
                # Must propagate — never silently swallow shutdown signals.
                raise
            except Exception as exc:
                exc_holder.append(exc)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.config.max_execution_time_seconds)

        # Collect and truncate output
        raw_stdout = stdout_buf.getvalue()
        raw_stderr = stderr_buf.getvalue()
        stdout, stdout_cut = _truncate(raw_stdout, _MAX_OUTPUT_BYTES)
        stderr, stderr_cut = _truncate(raw_stderr, _MAX_OUTPUT_BYTES)
        outcome["stdout"] = stdout
        outcome["stderr"] = stderr

        if stdout_cut or stderr_cut:
            outcome["truncated"] = True
            trunc_note = (
                f"\n[SANDBOX TRUNCATED] Output exceeded {_MAX_OUTPUT_BYTES} "
                "bytes and was cut. Only the first portion is shown."
            )
            outcome["error"] = (outcome.get("error") or "") + trunc_note

        # Timeout check
        if thread.is_alive():
            partial = stdout or stderr or "(no output captured)"
            timeout_msg = (
                f"[SANDBOX TIMEOUT] Code exceeded the "
                f"{self.config.max_execution_time_seconds}s execution limit. "
                f"Partial output:\n{partial}"
            )
            outcome["error"] = timeout_msg
            outcome["observation"] = timeout_msg
            return outcome

        # Final-answer signal
        if fa_holder:
            outcome["final_answer"] = fa_holder[0]

        # Runtime exception
        if exc_holder:
            exc = exc_holder[0]
            outcome["error"] = f"{type(exc).__name__}: {exc}"

        # Build the observation string the agent loop feeds to the LLM
        parts: List[str] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"[stderr]\n{stderr}")
        if outcome["error"]:
            parts.append(outcome["error"])
        if fa_holder:
            parts.append(f"[final_answer submitted: {fa_holder[0][:120]}]")
        if not parts:
            parts.append("(sandbox executed successfully, no output)")

        outcome["observation"] = "\n".join(parts)
        return outcome
