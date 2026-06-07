"""
Dynamic sandbox manual generator.

Builds a human-readable description of every tool available in the sandbox
so the LLM system prompt always reflects the actual set of tools.

Usage
-----
    # From discovered MCP tools (typical runtime path)
    from mcp_servers.mcp_client import MCPClient
    from sandbox.manual.generator import generate_manual_from_client

    client = MCPClient()
    client.connect_stdio("python mcp_tools_swebench.py")
    manual = generate_manual_from_client(client)

    # From a raw schema dict (e.g. for tests)
    manual = generate_manual_from_schemas({"run_tests": {...}, ...})
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_servers.mcp_client import MCPClient


_FINAL_ANSWER_DOC = """
Tool: final_answer
Signature: final_answer(answer: str) -> None
Description: Signal task completion.  Pass the final answer (or the result of
             get_patch() for SWE-bench) as a string.  This terminates the
             agent loop and is ALWAYS available regardless of the MCP server.
"""


def generate_manual_from_client(client: "MCPClient") -> str:
    """Return a manual string built from the tools discovered by *client*."""
    return generate_manual_from_schemas(client.discover_tools())


def generate_manual_from_schemas(schemas: dict[str, Any]) -> str:
    """
    Build the manual from a dict of {tool_name: schema_dict}.

    Each schema_dict may have "description" and "inputSchema" keys, following
    the MCP tool schema format.
    """
    sections: list[str] = []

    for name, schema in sorted(schemas.items()):
        description = schema.get("description") or "No description."
        input_schema = schema.get("inputSchema") or {}
        properties = input_schema.get("properties") or {}
        required = set(input_schema.get("required") or [])

        if properties:
            params = []
            for param_name, param_info in properties.items():
                ptype = param_info.get("type", "any")
                marker = "" if param_name in required else "?"
                params.append(f"{param_name}{marker}: {ptype}")
            signature = f"{name}({', '.join(params)})"
        else:
            signature = f"{name}()"

        sections.append(
            f"Tool: {name}\n"
            f"Signature: {signature}\n"
            f"Description: {description}"
        )

    if not sections:
        tool_block = "(no tools discovered)"
    else:
        tool_block = "\n\n".join(sections)

    return (
        "=== SANDBOX MANUAL ===\n\n"
        "The following tools are available as Python callables in the sandbox.\n"
        "Call them like regular functions — they communicate with the MCP server.\n\n"
        + tool_block
        + "\n"
        + _FINAL_ANSWER_DOC
        + "\n=== END OF MANUAL ==="
    )
