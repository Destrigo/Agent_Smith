from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve
from shared_tools._docker import is_docker_mode, docker_write_file


@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """
    Write *content* to *filepath*, creating or completely overwriting the file.

    Use this when:
    - You need to create a new file that doesn't exist yet.
    - edit_file() can't match the existing content (e.g. the file is binary or
      the exact string is hard to reproduce).
    - You want to replace the entire file at once.

    Returns a confirmation message or an error string.
    """
    if is_docker_mode():
        try:
            docker_write_file(filepath, content)
            return f"OK: written {filepath}"
        except Exception as e:
            return f"ERROR writing {filepath}: {e}"

    resolved = _resolve(filepath)
    try:
        import os
        os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: written {resolved}"
    except Exception as e:
        return f"ERROR writing {resolved}: {e}"
