import ast
import builtins as _builtins
import io
import os
import threading
from typing import Any, Dict, List, Optional

try:
    import resource as _resource
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False  # Windows / restricted environments

from models.sandbox_model import SandboxConfig


class FinalAnswerSignal(Exception):
    """Raised inside the sandbox when final_answer() is called.

    Inherits from Exception (not BaseException) so exam test code that wraps
    the call in `except Exception` can catch it and continue execution.
    In normal agent use final_answer() is never wrapped in a try/except,
    so this does not affect the agent loop's behaviour.
    """

    def __init__(self, answer: str):
        self.answer = answer
        super().__init__(f"final_answer called: {answer[:80]}")


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


def _current_vas_bytes() -> int:
    """Return the process's current virtual address space in bytes (Linux only)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


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
    ) -> Any:
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

    def _restricted_open(self, path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
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

        # Inject a custom print() into the sandbox namespace that writes to
        # our StringIO buffers instead of the real sys.stdout/sys.stderr.
        #
        # We deliberately avoid redirect_stdout/redirect_stderr context
        # managers here.  In Python 3.14, thread.start() blocks until the
        # new thread reaches a "running" state.  When the thread's first
        # action is setattr(sys, 'stdout', buf) (inside redirect_stdout),
        # there is a race: the thread can redirect sys.stdout before the
        # main thread's next print() executes, silently swallowing all CLI
        # output.  Injecting print() into the exec namespace avoids touching
        # the global sys.stdout entirely.

        def _sandbox_print(*args: Any, sep: str = " ", end: str = "\n", file: Any = None, flush: bool = False) -> None:
            import sys as _sys
            if file is None or file is _sys.stdout:
                target = stdout_buf
            elif file is _sys.stderr:
                target = stderr_buf
            else:
                target = file
            text = sep.join(str(a) for a in args) + end
            target.write(text)

        # Execute in a per-step snapshot so that a timed-out thread cannot
        # mutate self._namespace while the next step's thread is also running.
        # On success the snapshot is merged back; on timeout it is discarded
        # and self._namespace is left unchanged from before this call.
        ns_snapshot = dict(self._namespace)
        ns_snapshot["print"] = _sandbox_print

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
                exec(code, ns_snapshot)  # noqa: S102
                outcome["success"] = True
            except FinalAnswerSignal as fa:
                outcome["success"] = True
                fa_holder.append(fa.answer)
            except MemoryError:
                exc_holder.append(
                    MemoryError(
                        f"[SANDBOX MEMORY LIMIT] Code exceeded the "
                        f"{self.config.max_memory_mb}MB memory limit."
                    )
                )
            except (KeyboardInterrupt, SystemExit):
                # Must propagate — never silently swallow shutdown signals.
                raise
            except Exception as exc:
                exc_holder.append(exc)

        # --- Memory limit: set BEFORE thread.start() to close the race window.
        #
        # Setting it after thread.start() creates a race: the daemon thread can
        # call mmap/malloc (e.g. bytearray(512 MB)) and return before the main
        # thread reaches setrlimit, letting the allocation succeed even though it
        # exceeds the configured limit.
        #
        # RLIMIT_AS is process-wide; we restore it from the main thread after
        # join() so even a timed-out (still-alive) thread doesn't leave the
        # reduced limit in place for subsequent sandbox calls.
        #
        # The limit is:  current_VAS  +  thread-stack headroom (16 MB)
        #                             +  max_memory_mb
        # so the sandbox code has exactly max_memory_mb of additional virtual
        # space while still leaving room for the thread stack that is mmap'd
        # during thread.start().  Setting an absolute cap of max_memory_mb
        # would be below Python's own VAS baseline and would crash the process.
        _THREAD_STACK_HEADROOM = 16 * 1024 * 1024  # 16 MB
        _orig_as = None
        if _HAS_RESOURCE and self.config.max_memory_mb > 0:
            try:
                _extra = self.config.max_memory_mb * 1024 * 1024
                _current_vas = _current_vas_bytes()
                _base = _current_vas or 512 * 1024 * 1024
                _max = _base + _THREAD_STACK_HEADROOM + _extra
                _orig_as = _resource.getrlimit(_resource.RLIMIT_AS)
                _cur_soft = _orig_as[0]
                _unlimited = _resource.RLIM_INFINITY
                if _cur_soft == _unlimited or _cur_soft > _max:
                    _resource.setrlimit(
                        _resource.RLIMIT_AS,
                        (_max, _orig_as[1]),
                    )
            except Exception:
                _orig_as = None

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        thread.join(timeout=self.config.max_execution_time_seconds)

        # Always restore — even if join timed out.
        if _HAS_RESOURCE and _orig_as is not None:
            try:
                _resource.setrlimit(_resource.RLIMIT_AS, _orig_as)
            except Exception:
                pass

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
            # Inject TimeoutError into the thread so bare-except loops can be
            # interrupted (layer 0.5). Without this, a `except: pass` loop
            # would run forever since thread.join() never raises in the thread.
            try:
                import ctypes as _ctypes
                _ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    _ctypes.c_ulong(thread.ident or 0),
                    _ctypes.py_object(TimeoutError),
                )
                thread.join(timeout=3)
            except Exception:
                pass

            # Collect any additional output produced after the injection.
            raw_stdout = stdout_buf.getvalue()
            raw_stderr = stderr_buf.getvalue()
            stdout, stdout_cut = _truncate(raw_stdout, _MAX_OUTPUT_BYTES)
            stderr, stderr_cut = _truncate(raw_stderr, _MAX_OUTPUT_BYTES)
            outcome["stdout"] = stdout
            outcome["stderr"] = stderr

            # ns_snapshot may be partially written by the still-running thread;
            # discard it so self._namespace stays in the last known-good state.
            partial = stdout or stderr or "(no output captured)"
            timeout_msg = (
                f"[SANDBOX TIMEOUT] Code exceeded the "
                f"{self.config.max_execution_time_seconds}s execution limit. "
                f"Partial output:\n{partial}"
            )
            outcome["error"] = timeout_msg
            outcome["observation"] = timeout_msg
            return outcome

        # Thread completed — merge snapshot back into the persistent namespace.
        self._namespace.update(ns_snapshot)

        # Final-answer signal
        if fa_holder:
            outcome["final_answer"] = fa_holder[0]

        # Runtime exception
        if exc_holder:
            exc = exc_holder[0]
            if isinstance(exc, MemoryError):
                # Already has a [SANDBOX MEMORY LIMIT] prefix from _run().
                outcome["error"] = str(exc)
            else:
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
