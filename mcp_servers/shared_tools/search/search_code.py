import os
import fnmatch
from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed

_MAX_RESULTS = 200


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*"):
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
                            if len(results) >= _MAX_RESULTS:
                                results.append(
                                    f"[TRUNCATED: more than {_MAX_RESULTS} "
                                    "matches found, refine your pattern]")
                                return results
            except Exception:
                continue

    return results