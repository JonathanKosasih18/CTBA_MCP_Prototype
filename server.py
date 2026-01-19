# Import the server instance
from server_instance import mcp

# Import tools and prompts to register them with the server
import tools
import prompts

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    mcp.run(transport="sse")