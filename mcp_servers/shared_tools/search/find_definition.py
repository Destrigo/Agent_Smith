import os
import re
from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed

_MAX_RESULTS = 200


@mcp.tool()
def search_function_or_class_definition_in_code(name: str):
    results = []

    pattern = re.compile(rf"^\s*(def|class)\s+{re.escape(name)}\b")

    for root, _, files in os.walk(testbed()):
        for file in files:
            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append(
                                f"{path}:{i} {line.rstrip()}"
                            )
                            if len(results) >= _MAX_RESULTS:
                                results.append(
                                    f"[TRUNCATED: more than {_MAX_RESULTS} "
                                    "definitions found]")
                                return results
            except Exception:
                continue

    return results