from mcp_server import mcp_server as mcp


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """
    Replace the first occurrence of old_str with new_str in the given file.
    Returns a confirmation message or an error if old_str was not found.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if old_str not in content:
        return f"ERROR: string not found in {filepath}"

    new_content = content.replace(old_str, new_str, 1)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"OK: replaced in {filepath}"
