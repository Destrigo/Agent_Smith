import os
import fnmatch

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed
from shared_tools._docker import is_docker_mode, docker_search_code


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*"):
    if is_docker_mode():
        return docker_search_code(pattern, "/testbed", file_pattern)

    results = []

    for root, _, files in os.walk(testbed()):
        for file in files:

            if not fnmatch.fnmatch(file, file_pattern):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        if pattern in line:
                            results.append(
                                f"{path}:{i} {line.rstrip()}"
                            )
            except Exception:
                continue

    return results
