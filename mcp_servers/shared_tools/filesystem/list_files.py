import os
import fnmatch
from typing import cast

from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve
from shared_tools._docker import is_docker_mode, docker_list_files


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> list[str]:
    """
    List files in a directory matching a glob pattern.
    """
    if is_docker_mode():
        return cast(list[str], docker_list_files(directory, pattern))

    directory = _resolve(directory)
    if not os.path.exists(directory):
        return []

    results = []

    for root, _, files in os.walk(directory):
        for file in files:
            if fnmatch.fnmatch(file, pattern):
                results.append(os.path.join(root, file))

    return results
