# Import the server instance
from server_instance import mcp

# Import tools and prompts to register them with the server
import tools
import prompts

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    mcp.run(transport="streamable-http")
    # mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)