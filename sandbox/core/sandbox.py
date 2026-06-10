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
    """Inherits from Exception so test code can catch it; BaseException would bypass bare except."""

    def __init__(self, answer: str):
        self.answer = answer
        super().__init__(f"final_answer called: {answer[:80]}")


_BLOCKED_MODULES: frozenset[str] = frozenset({
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

_BLOCKED_BUILTINS: frozenset[str] = frozenset({
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

_MAX_OUTPUT_BYTES: int = 8192


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="replace"), True


def _current_vas_bytes() -> int:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


class Sandbox:
    """Executes LLM-generated Python code in an isolated namespace.

    Runs in a daemon thread (not subprocess) so the namespace persists across steps.
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
        for name, fn in tools.items():
            self._namespace[name] = fn

    def _final_answer_fn(self, answer: str) -> None:
        raise FinalAnswerSignal(str(answer))

    def _make_safe_builtins(self) -> dict[str, Any]:
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
        globals: Optional[dict[str, Any]] = None,
        locals: Optional[dict[str, Any]] = None,
        fromlist: tuple[str, ...] = (),
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

    @staticmethod
    def no_code_feedback() -> dict[str, Any]:
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
        return (
            f"[SANDBOX WARNING] The code block was malformed. "
            f"It was interpreted as:\n```python\n{interpreted}\n```\n"
            f"Original response snippet:\n{original[:200]}"
        )

    def execute(self, code: str) -> dict[str, Any]:
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

        # inject print() into the namespace instead of redirect_stdout to avoid a
        # thread-start race in Python 3.14 that silently swallows CLI output
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

        # per-step snapshot: merged back on success, discarded on timeout
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

        # set RLIMIT_AS before thread.start() to close the allocation race window;
        # cap = current_VAS + stack headroom + max_memory_mb (not an absolute cap
        # or we'd be below Python's own baseline and crash)
        _THREAD_STACK_HEADROOM = 16 * 1024 * 1024
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

        # always restore — even if join timed out
        if _HAS_RESOURCE and _orig_as is not None:
            try:
                _resource.setrlimit(_resource.RLIMIT_AS, _orig_as)
            except Exception:
                pass

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
            # raise TimeoutError in the thread via ctypes so bare-except loops can be interrupted
            try:
                import ctypes as _ctypes
                _ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    _ctypes.c_ulong(thread.ident or 0),
                    _ctypes.py_object(TimeoutError),
                )
                thread.join(timeout=3)
            except Exception:
                pass

            raw_stdout = stdout_buf.getvalue()
            raw_stderr = stderr_buf.getvalue()
            stdout, stdout_cut = _truncate(raw_stdout, _MAX_OUTPUT_BYTES)
            stderr, stderr_cut = _truncate(raw_stderr, _MAX_OUTPUT_BYTES)
            outcome["stdout"] = stdout
            outcome["stderr"] = stderr

            partial = stdout or stderr or "(no output captured)"
            timeout_msg = (
                f"[SANDBOX TIMEOUT] Code exceeded the "
                f"{self.config.max_execution_time_seconds}s execution limit. "
                f"Partial output:\n{partial}"
            )
            outcome["error"] = timeout_msg
            outcome["observation"] = timeout_msg
            return outcome

        self._namespace.update(ns_snapshot)

        if fa_holder:
            outcome["final_answer"] = fa_holder[0]

        if exc_holder:
            exc = exc_holder[0]
            if isinstance(exc, MemoryError):
                # Already has a [SANDBOX MEMORY LIMIT] prefix from _run().
                outcome["error"] = str(exc)
            else:
                outcome["error"] = f"{type(exc).__name__}: {exc}"

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
