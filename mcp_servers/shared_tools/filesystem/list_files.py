import os
import fnmatch
from mcp_server import mcp_server as mcp

@mcp.tool()
def list_files(directory: str, pattern: str) -> list[str]:
    """
    List files in a directory matching a glob pattern.
    """
    if not os.path.exists(directory):
        return []
    
    results = []

    for root, _, files in os.walk(directory):
        for file in files:
            if fnmatch.fnmatch(file, pattern):
                results.append(os.path.join(root, file))

    return results