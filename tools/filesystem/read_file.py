# @mcp.tool()
def read_file(
    filepath: str,
    start_line: int = 1,
    end_line: int = 50
    ) -> str:
    with open(filepath) as f:
        lines = f.readlines()

    result = []

    for i, line in enumerate(
        lines[start_line-1:end_line],
        start=start_line
    ):
        result.append(f"{i}: {line}")

    return "".join(result)