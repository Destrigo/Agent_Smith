import os
import re

from mcp_server import mcp_server as mcp
from shared_tools._testbed import testbed
from shared_tools._docker import is_docker_mode, docker_exec


@mcp.tool()
def find_references(name: str, filepath: str = "", line: int = 0):
    if is_docker_mode():
        cmd = (
            f"grep -rn --include='*.py' -E "
            f"'\\b{re.escape(name)}\\b' /testbed 2>/dev/null || true"
        )
        result = docker_exec(cmd, workdir="/testbed")
        lines = result["stdout"].strip().splitlines()
        return [l for l in lines if l]

    results = []

    # word boundary to avoid partial matches
    pattern = re.compile(rf"\b{name}\b")

    for root, _, files in os.walk(testbed()):
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
