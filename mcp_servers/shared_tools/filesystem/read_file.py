from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve
from shared_tools._docker import is_docker_mode, docker_read_file


@mcp.tool()
def read_file(filepath: str, start_line: int = 1, end_line: int = 9999) -> str:
    """
    Read lines [start_line, end_line] (1-indexed, inclusive) from a file.
    Returns the lines prefixed with their line numbers.
    """
    if is_docker_mode():
        try:
            content = docker_read_file(filepath)
        except FileNotFoundError as e:
            return f"ERROR: {e}"
        lines = content.splitlines(keepends=True)
        total = len(lines)
        start = max(1, start_line)
        end = min(total, end_line)
        if start > total:
            return (
                f"ERROR: start_line {start_line} exceeds "
                f"file length ({total} lines): {filepath}"
            )
        result = []
        for i, line in enumerate(lines[start - 1:end], start=start):
            result.append(f"{i}: {line}")
        return "".join(result)

    filepath = _resolve(filepath)
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"ERROR: file not found: {filepath}"
    except PermissionError:
        return f"ERROR: permission denied: {filepath}"
    except Exception as e:
        return f"ERROR reading {filepath}: {e}"

    total = len(lines)
    start = max(1, start_line)
    end = min(total, end_line)

    if start > total:
        return (
            f"ERROR: start_line {start_line} exceeds "
            f"file length ({total} lines): {filepath}"
        )

    result = []
    for i, line in enumerate(lines[start - 1:end], start=start):
        result.append(f"{i}: {line}")
    return "".join(result)
