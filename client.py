import asyncio
import os
import json
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.types import CallToolResult
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class Client:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.llm = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    async def connect(self):
        print(f"🔌 Connecting to server at {self.server_url}...")
        self.transport = await self.exit_stack.enter_async_context(
            sse_client(self.server_url)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.transport[0], self.transport[1])
        )
        await self.session.initialize()
        print("✅ Session Initialized!")

    async def list_tools_for_llm(self):
        """
        Fetches tools from MCP and converts them to OpenAI's JSON schema format.
        """
        if not self.session:
            raise RuntimeError("Not connected")

        response = await self.session.list_tools()
        
        openai_tools = []
        for tool in response.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })
        return openai_tools

    async def process_query(self, user_query: str):
        """
        The 'Agent Loop': 
        1. User asks question -> LLM decides if it needs a tool.
        2. If tool needed -> Client runs tool -> returns result to LLM.
        3. LLM analyzes result -> Answers user.
        """
        messages = [{"role": "user", "content": user_query}]
        tools = await self.list_tools_for_llm()

        print(f"\n🤖 Thinking about: '{user_query}'...")

        response = await self.llm.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        initial_msg = response.choices[0].message
        
        # Check if the LLM wants to use a tool
        if initial_msg.tool_calls:
            messages.append(initial_msg) # Keep conversation history
            
            for tool_call in initial_msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(f"⚡ LLM invoking tool: {func_name} with args {func_args}")
                
                # Execute the tool on the MCP Server
                result = await self.session.call_tool(func_name, arguments=func_args)
                
                # Extract text content from the result
                tool_output = "\n".join(
                    [c.text for c in result.content if c.type == "text"]
                )
                print(f"📊 Tool Data Received ({len(tool_output)} chars)")

                # Feed the result back to the LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output
                })

            # --- Second Pass: LLM analyzes the data ---
            final_response = await self.llm.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            return final_response.choices[0].message.content
        
        else:
            # If no tools were needed
            return initial_msg.content

    async def close(self):
        await self.exit_stack.aclose()
        print("🔌 Connection closed.")

# --- Usage  ---
async def main():
    CLIENT = Client(server_url="http://127.0.0.1:8000/sse")
    
    try:
        await CLIENT.connect()
        
        # Query here
        answer = await CLIENT.process_query(
            "List all the tools available on the server and their descriptions."
        )
        print("\n📝 FINAL ANSWER:\n" + answer)

    finally:
        await CLIENT.close()

if __name__ == "__main__":
    asyncio.run(main())