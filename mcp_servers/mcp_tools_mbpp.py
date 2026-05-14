from mcp_server import mcp_server
import shared_tools.execution.get_patch
import shared_tools.execution.run_command
import shared_tools.execution.run_tests
import shared_tools.filesystem.edit_file
import shared_tools.filesystem.read_file
import shared_tools.filesystem.list_files
import shared_tools.search.search_code
import shared_tools.search.find_definition
import shared_tools.search.find_references

# print("MCP Server is running with the following tools:")
# for tool in mcp_server.tools:
#     print(f"- {tool.name}")
