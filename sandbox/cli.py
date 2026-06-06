"""
sandbox CLI entry point.

    uv run sandbox                            interactive REPL, default config
    uv run sandbox sandbox_template.json      load config from file
    uv run sandbox cfg.json --mcp-stdio "python mcp_tools_mbpp.py"
    uv run sandbox cfg.json --mcp-server http://localhost:8000/mcp
"""

import argparse
import json
import sys

from models.sandbox_model import SandboxConfig
from sandbox.core.sandbox import Sandbox


def _read_multiline(prompt: str) -> str | None:
    """Read code from stdin until a blank line is entered.

    In non-interactive (pipe) mode the entire stdin is consumed at once so
    that multi-line scripts with blank lines work correctly.

    Returns None when stdin is exhausted (EOF with no input collected),
    so callers can detect pipe-closed / non-interactive termination.
    """
    # Pipe / redirect mode: read everything at once
    if not sys.stdin.isatty():
        code = sys.stdin.read()
        return code if code.strip() else None

    # Interactive REPL mode: read until blank line or EOF
    print(prompt)
    lines: list[str] = []
    while True:
        try:
            line = input("... " if lines else ">>> ")
        except EOFError:
            if not lines:
                return None
            break
        if line == "" and lines:
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sandbox",
        description="Run LLM-generated Python code in an isolated sandbox.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Path to a SandboxConfig JSON file (optional).",
    )
    parser.add_argument(
        "--mcp-stdio",
        metavar="COMMAND",
        default=None,
        help="Launch an MCP server subprocess and connect via stdio.",
    )
    parser.add_argument(
        "--mcp-server",
        metavar="URL",
        default=None,
        help="Connect to an already-running MCP server via streamable HTTP.",
    )
    args = parser.parse_args()

    # setup
    if args.config:
        with open(args.config, "r") as f:
            config_data = json.load(f)
        config = SandboxConfig(**config_data)
    else:
        config = SandboxConfig()

    sandbox = Sandbox(config)

    # MCP connection
    if args.mcp_stdio or args.mcp_server:
        try:
            from mcp_servers.mcp_client import MCPClient

            client = MCPClient()

            if args.mcp_stdio:
                cmd_parts = args.mcp_stdio.split()
                client.connect_stdio(cmd_parts[0], cmd_parts[1:])
                print(f"[sandbox] Connected to MCP server via stdio: {args.mcp_stdio}")
            else:
                client.connect_http(args.mcp_server)
                print(f"[sandbox] Connected to MCP server via HTTP: {args.mcp_server}")

            tools = client.make_tool_wrappers()
            sandbox.register_mcp_tools(tools)
            print(f"[sandbox] Registered {len(tools)} MCP tools: {list(tools)}")

        except Exception as exc:
            print(f"[sandbox] WARNING: could not connect to MCP server — {exc}",
                  file=sys.stderr)

    # repl
    print("\n[sandbox] Ready.  Enter Python code (blank line to execute, Ctrl-D to quit).\n")

    while True:
        try:
            code = _read_multiline("Enter code:")
        except KeyboardInterrupt:
            print()
            continue

        if code is None:
            # stdin exhausted (pipe closed) — exit cleanly
            break

        if not code.strip():
            continue

        result = sandbox.execute(code)

        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)
        if result["error"]:
            print(f"[error] {result['error']}", file=sys.stderr)
        if result["final_answer"] is not None:
            print(f"\n[final_answer] {result['final_answer']}")
            break


if __name__ == "__main__":
    main()
