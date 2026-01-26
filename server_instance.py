from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "CTBA MCP",
    transport_security=TransportSecuritySettings(
        allowed_hosts=["*"] 
    )
)