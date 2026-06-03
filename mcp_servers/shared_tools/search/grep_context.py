import os
import fnmatch

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed
from shared_tools._docker import is_docker_mode, docker_exec


@mcp.tool()
def grep_context(pattern: str, context_lines: int = 5,
                 file_pattern: str = "*.py") -> list[str]:
    """
    Search for *pattern* in all matching files and return each hit together
    with *context_lines* lines of surrounding context — like ``grep -n -C``.

    Returns a list of strings, one per match, each block separated with ---.
    More efficient than search_code() + read_file(): finds AND shows context
    in a single tool call.

    Example: grep_context("cotm", context_lines=5, file_pattern="*.py")
    """
    if is_docker_mode():
        cmd = (
            f"grep -rn -C {context_lines} --include='{file_pattern}' "
            f"-F {_shell_quote(pattern)} /testbed 2>/dev/null || true"
        )
        result = docker_exec(cmd, workdir="/testbed")
        lines = result["stdout"].strip().splitlines()
        return [ln for ln in lines if ln]

    results = []
    base = testbed()

    for root, _, files in os.walk(base):
        for file in files:
            if not fnmatch.fnmatch(file, file_pattern):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
            except Exception:
                continue

            for i, line in enumerate(all_lines):
                if pattern in line:
                    lo = max(0, i - context_lines)
                    hi = min(len(all_lines), i + context_lines + 1)
                    block = [f"{path}:{i + 1}: {line.rstrip()}"]
                    for j in range(lo, hi):
                        prefix = ">" if j == i else " "
                        block.append(
                            f"{path}:{j + 1}{prefix} {all_lines[j].rstrip()}"
                        )
                    results.append("\n".join(block))
                    results.append("---")

    return results


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"
