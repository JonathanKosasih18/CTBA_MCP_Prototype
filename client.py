import asyncio
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    """
    Docstring for main
    """
    async with sse_client(url="http://localhost:8000/mcp/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.send_ping()
            tools = await session.list_tools()
            print("Available Tools:")

            for tool in tools.tools: 
                print("Name: ", tool.name)
                print("Description: ", tool.description)
            print()

asyncio.run(main())
