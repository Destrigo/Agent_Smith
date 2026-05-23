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
    "os", "sys", "subprocess", "socket", "urllib", "http", "ftplib",
    "smtplib", "ssl", "shutil", "importlib", "ctypes", "cffi",
    "multiprocessing", "threading", "concurrent", "asyncio",
    "pickle", "shelve", "marshal", "tempfile", "signal", "resource",
    "pty", "rlcompleter", "code", "codeop", "readline",
    "_thread", "gc", "weakref",
})

# Builtins that are always removed from the sandbox namespace.
_BLOCKED_BUILTINS: frozenset = frozenset({
    "eval", "exec", "compile", "__import__",
    "open", "input",
    "__loader__", "__spec__", "__build_class__",
    "breakpoint",
})


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

    Design decision — in-process threading
    ---------------------------------------
    We execute code in a daemon thread rather than a subprocess so that the
    sandbox namespace persists across steps.  The thread is joined with a
    timeout; if it is still alive after the deadline the result is marked as
    timed-out and the thread is left to die on its own (daemon=True ensures it
    won't block process exit).  This is the accepted trade-off for persistent
    state: true process isolation would require serialising the namespace.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._namespace: Dict[str, Any] = {}
        self._setup_namespace()

    # ------------------------------------------------------------------
    # Namespace setup
    # ------------------------------------------------------------------

    def _setup_namespace(self) -> None:
        self._namespace = {
            "__builtins__": self._make_safe_builtins(),
            "final_answer": self._final_answer_fn,
        }

    def register_mcp_tools(self, tools: Dict[str, Any]) -> None:
        """Inject MCP tool callables into the sandbox namespace."""
        for name, fn in tools.items():
            self._namespace[name] = fn

    # ------------------------------------------------------------------
    # final_answer
    # ------------------------------------------------------------------

    def _final_answer_fn(self, answer: str) -> None:
        raise FinalAnswerSignal(str(answer))

    # ------------------------------------------------------------------
    # Restricted builtins
    # ------------------------------------------------------------------

    def _make_safe_builtins(self) -> dict:
        safe = {
            k: v for k, v in vars(_builtins).items()
            if k not in _BLOCKED_BUILTINS
        }
        safe["__import__"] = self._restricted_import
        safe["open"] = self._restricted_open
        return safe

    # ------------------------------------------------------------------
    # Import restriction
    # ------------------------------------------------------------------

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
                f"Import of '{name}' is blocked in the sandbox "
                f"(module is on the deny list)."
            )
        if not self._is_import_allowed(name):
            raise ImportError(
                f"Import of '{name}' is not allowed. "
                f"Authorized imports: {self.config.authorized_imports}"
            )
        return _builtins.__import__(name, globals, locals, fromlist, level)

    # ------------------------------------------------------------------
    # Filesystem restriction
    # ------------------------------------------------------------------

    def _restricted_open(self, path, mode="r", *args, **kwargs):
        abs_path = os.path.realpath(str(path))
        for allowed in self.config.allowed_directories:
            allowed_real = os.path.realpath(allowed)
            if abs_path == allowed_real or abs_path.startswith(allowed_real + os.sep):
                return _builtins.open(path, mode, *args, **kwargs)
        raise PermissionError(
            f"File access to '{path}' is not allowed. "
            f"Allowed directories: {self.config.allowed_directories}"
        )

    # ------------------------------------------------------------------
    # Code execution
    # ------------------------------------------------------------------

    def execute(self, code: str) -> dict:
        """
        Execute *code* inside the sandbox.

        Returns a dict with keys:
            success      bool
            stdout       str
            stderr       str
            error        str | None  — exception message, or timeout/syntax notice
            final_answer str | None  — value passed to final_answer(), if called
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"SyntaxError: {e}",
                "final_answer": None,
            }

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        outcome: Dict[str, Any] = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": None,
            "final_answer": None,
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
                raise
            except Exception as exc:
                exc_holder.append(exc)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.config.max_execution_time_seconds)

        outcome["stdout"] = stdout_buf.getvalue()
        outcome["stderr"] = stderr_buf.getvalue()

        if thread.is_alive():
            outcome["error"] = (
                f"ExecutionTimeout: code exceeded the "
                f"{self.config.max_execution_time_seconds}s limit. "
                "Partial output is shown above."
            )
            return outcome

        if fa_holder:
            outcome["final_answer"] = fa_holder[0]

        if exc_holder:
            exc = exc_holder[0]
            outcome["error"] = f"{type(exc).__name__}: {exc}"

        return outcome
