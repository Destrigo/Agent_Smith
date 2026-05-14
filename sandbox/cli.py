import argparse
import json

from sandbox_model import SandboxConfig
from sandbox import Sandbox


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("config", nargs="?", default=None)
    parser.add_argument("--mcp-stdio", default=None)
    parser.add_argument("--mcp-server", default=None)

    args = parser.parse_args()

    if args.config:
        with open(args.config, "r") as f:
            config_data = json.load(f)
        config = SandboxConfig(**config_data)

    else:
        config = SandboxConfig()

    print("Sandbox started")
    print(config)

    if args.mcp_stdio:
        print("Using MCP stdio:", args.mcp_stdio)

    if args.mcp_server:
        print("Using MCP server:", args.mcp_server)

    sandbox = Sandbox(config)

    while True:

        print("\nEnter code:")
        code = input(">>> ")

        result = sandbox.execute(code)

        print(result)


if __name__ == "__main__":
    main()