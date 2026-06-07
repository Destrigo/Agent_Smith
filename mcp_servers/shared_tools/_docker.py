"""
Docker execution helper for SWE-bench MCP tools.

When DOCKER_CONTAINER_ID is set, all tool operations (read, write, exec,
search) are routed through Docker exec / put_archive instead of the local
filesystem.  When it is not set, callers fall back to the local path.
"""
import io
import os
import tarfile as _tarfile
from typing import Any, Optional


def _container_id() -> Optional[str]:
    return os.environ.get("DOCKER_CONTAINER_ID")


def _get_container() -> Any:
    import docker
    cid = _container_id()
    client = docker.from_env()
    return client.containers.get(cid)


# ── read ──────────────────────────────────────────────────────────────────────

def docker_read_file(filepath: str) -> str:
    container = _get_container()
    exit_code, output = container.exec_run(["cat", filepath])
    if exit_code != 0:
        raise FileNotFoundError(
            f"Cannot read {filepath} from container: "
            f"{output.decode('utf-8', errors='replace')}"
        )
    return str(output.decode("utf-8", errors="replace"))


# ── write ─────────────────────────────────────────────────────────────────────

def _write_file_to_container(container: Any, filepath: str, content: str) -> None:
    """Low-level write: pack content into a tar and put_archive into container."""
    content_bytes = content.encode("utf-8")
    buf = io.BytesIO()
    filename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath) or "/"
    with _tarfile.open(fileobj=buf, mode="w") as tar:
        info = _tarfile.TarInfo(name=filename)
        info.size = len(content_bytes)
        info.uid = 0
        info.gid = 0
        tar.addfile(info, io.BytesIO(content_bytes))
    buf.seek(0)
    container.put_archive(dirpath, buf)


def docker_write_file(filepath: str, content: str) -> None:
    _write_file_to_container(_get_container(), filepath, content)


# ── exec ──────────────────────────────────────────────────────────────────────

def docker_exec(command: str, workdir: str = "/testbed",
                timeout: int = 30) -> dict[str, Any]:
    """Run a shell command inside the container, return stdout/stderr/exit_code."""
    container = _get_container()
    result = container.exec_run(
        ["bash", "-c", command],
        workdir=workdir,
        demux=True,
    )
    stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
    stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.exit_code,
    }


# ── list ──────────────────────────────────────────────────────────────────────

def docker_list_files(directory: str, pattern: str = "*") -> list[str]:
    result = docker_exec(f"find {directory} -type f -name '{pattern}'",
                         workdir=directory)
    if result["exit_code"] != 0:
        return []
    lines = result["stdout"].strip().splitlines()
    return [ln for ln in lines if ln]


# ── search ────────────────────────────────────────────────────────────────────

def docker_search_code(pattern: str, directory: str,
                       file_pattern: str = "*") -> list[str]:
    cmd = f"grep -rn --include='{file_pattern}' -F {_shell_quote(pattern)} {directory} 2>/dev/null || true"
    result = docker_exec(cmd, workdir=directory)
    lines = result["stdout"].strip().splitlines()
    return [ln for ln in lines if ln]


def _shell_quote(s: str) -> str:
    """Minimally shell-quote a string for use in a grep -F argument."""
    return "'" + s.replace("'", "'\\''") + "'"


# ── convenience ───────────────────────────────────────────────────────────────

def is_docker_mode() -> bool:
    return bool(_container_id())
