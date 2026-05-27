from mcp_server import mcp_server as mcp
from shared_tools._testbed import _resolve
from shared_tools._docker import is_docker_mode, docker_read_file, docker_write_file


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """
    Replace the first occurrence of old_str with new_str in the given file.
    Returns a confirmation message or an error if old_str was not found.
    """
    if is_docker_mode():
        try:
            content = docker_read_file(filepath)
        except FileNotFoundError as e:
            return f"ERROR: {e}"
        if old_str not in content:
            return f"ERROR: string not found in {filepath}"
        new_content = content.replace(old_str, new_str, 1)
        docker_write_file(filepath, new_content)
        return f"OK: replaced in {filepath}"

    filepath = _resolve(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if old_str not in content:
        return f"ERROR: string not found in {filepath}"

    new_content = content.replace(old_str, new_str, 1)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"OK: replaced in {filepath}"
