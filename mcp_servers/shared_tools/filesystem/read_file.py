# @mcp.tool()
def read_file(
    filepath: str,
    start_line: int,
    end_line: int
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