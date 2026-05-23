from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP()


class MCPBridge:

    def call(self, tool_name, payload):

        # qui potresti:
        # - fare HTTP
        # - usare stdio
        # - websocket
        # - subprocess
        # - client MCP reale

        print(f"[MCP OUTSIDE] {tool_name} -> {payload}")

        if tool_name == "get_time":
            return {"time": "12:00"}

        return {"error": "unknown tool"}