from mcp_server.server import mcp as server_mcp


def generate_manual(server_mcp=server_mcp) -> str:
    """
    Generates the manual of all the tools the mcp can see with its wrapper.
    """
    return server.generate_manual()