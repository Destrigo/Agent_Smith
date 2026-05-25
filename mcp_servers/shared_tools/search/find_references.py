import os
import re
from mcp_server import mcp_server as mcp

@mcp.tool()
def find_references(name: str, filepath: str = "", line: int = 0):
    results = []

    # word boundary to avoid partial matches
    pattern = re.compile(rf"\b{name}\b")

    for root, _, files in os.walk("/testbed"):
        for file in files:
            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, l in enumerate(f, start=1):
                        if pattern.search(l):
                            results.append(
                                f"{path}:{i} {l.rstrip()}"
                            )
            except Exception:
                continue

    return results