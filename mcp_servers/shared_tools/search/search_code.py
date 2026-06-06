import os
import fnmatch
from typing import cast

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed
from shared_tools._docker import is_docker_mode, docker_search_code, docker_exec, _shell_quote


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*.py",
                directory: str = "") -> list[str]:
    """
    Search for *pattern* (fixed string, not regex) in all files matching
    *file_pattern* (filename glob, e.g. '*.py') under *directory*.

    If *directory* is omitted, the whole /testbed tree is searched.
    If *file_pattern* is a full path (starts with '/'), the pattern is
    searched in that specific file only.

    Returns a list of strings in the format  /path/file.py:<line> <content>
    """
    # Special case: file_pattern is actually a full path to a specific file
    if file_pattern.startswith("/"):
        specific_file = file_pattern
        if is_docker_mode():
            result = docker_exec(
                f"grep -n -F {_shell_quote(pattern)} {specific_file} 2>/dev/null || true",
                workdir="/testbed",
            )
            lines = result["stdout"].strip().splitlines()
            return [ln for ln in lines if ln]
        try:
            matches = []
            with open(specific_file, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, start=1):
                    if pattern in line:
                        matches.append(f"{specific_file}:{i} {line.rstrip()}")
            return matches
        except Exception as e:
            return [f"ERROR: {e}"]

    # Normal case: file_pattern is a glob, search recursively
    search_dir = directory or ("/testbed" if is_docker_mode() else testbed())

    if is_docker_mode():
        return cast(list[str], docker_search_code(pattern, search_dir, file_pattern))

    results = []
    for root, _, files in os.walk(search_dir):
        for file in files:
            if not fnmatch.fnmatch(file, file_pattern):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        if pattern in line:
                            results.append(f"{path}:{i} {line.rstrip()}")
            except Exception:
                continue
    return results
