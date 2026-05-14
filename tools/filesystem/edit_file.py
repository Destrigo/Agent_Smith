# @mcp.tool()
def edit_file(
    filepath: str,
    old_str: str,
    new_str: str
    ):
    with open(filepath) as f:
        lines = f.readlines()
        for line in lines:
            if old_str in line:
                line = line.replace(old_str, new_str)