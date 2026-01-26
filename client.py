import asyncio
import httpx
import os
import json
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult
from datetime import datetime
from openai import AsyncOpenAI
from utils.logger import logger
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self, server_url: str):
        """
        Initialize session and client objects.
        """
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.messages = []
        self.logger = logger
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def connect(self):
        """
        Connect to the MCP Server via SSE.
        """
        print(f"🔌 Connecting to MCP Server at {self.server_url}...")
        
        transport = await self.exit_stack.enter_async_context(
            sse_client(self.server_url)
        )
        
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(transport[0], transport[1])
        )
        
        await self.session.initialize()
        print("✅ MCP Session Initialized!")

    async def get_tools(self):
        """
        Get MCP Tool list from the server.
        """
        if not self.session:
            raise RuntimeError("Client not connected.")
            
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None):
        """
        Call an MCP Tool.
        """
        if not self.session:
            raise RuntimeError("Client not connected.")
            
        if arguments is None:
            arguments = {}
            
        print(f"🔨 Calling Tool: {tool_name} with args: {arguments}")
        result: CallToolResult = await self.session.call_tool(tool_name, arguments)
        return result
    
    def _convert_tool_format(self, mcp_tool) -> Dict:
        """
        Helper function: Convert MCP Tool to OpenAI Tool format.
        """
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "parameters": mcp_tool.inputSchema
            }
        }

    async def process_query(self, query: str):
        """
        Full Agent Loop: 
        1. Get Tools
        2. LLM Decides (Think)
        3. Execute Tool (Act) 
        4. LLM Synthesizes Answer (Response)
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": query})

        # Fetch tools and convert to OpenAI format
        mcp_tools = await self.get_tools()
        # openai_tools = [self._convert_tool_format(tool) for tool in mcp_tools]

        print("\n🤖 Thinking...")

        # --- START SIMULATION BLOCK ---
        # Instead of calling self.llm.chat.completions.create, we mock the decision.
        
        initial_msg = None
        
        # Simple keyword check to trigger the specific tool
        if "sales" in query.lower() or "transaction" in query.lower():
            print("✨ Simulation triggered: Deciding to fetch sales report...")
            
            # We construct a mock object that looks like an OpenAI Message with tool_calls
            class MockFunction:
                name = "fetch_deduplicated_sales_report"
                arguments = "{}" # Empty JSON arguments

            class MockToolCall:
                id = "call_sim_123"
                function = MockFunction()

            class MockMessage:
                tool_calls = [MockToolCall()]
                content = None
                role = "assistant"
            
            initial_msg = MockMessage()
            
        else:
            # Fallback for other queries
            class MockMessageNoTool:
                tool_calls = None
                content = "I am in simulation mode. Please ask me about 'transactions by salesmen'."
                role = "assistant"
            initial_msg = MockMessageNoTool()

        # --- END SIMULATION BLOCK ---

        # Check if "LLM" wants to use tools
        if initial_msg.tool_calls:
            self.messages.append({"role": "assistant", "content": None}) # Placeholder for history
            
            for tool_call in initial_msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                # Execute the tool
                try:
                    tool_result = await self.call_tool(func_name, func_args)
                    
                    # Extract text content from result
                    tool_output_text = "\n".join(
                        [c.text for c in tool_result.content if c.type == "text"]
                    )
                except Exception as e:
                    tool_output_text = f"Error executing tool: {str(e)}"
                    print(f"❌ {tool_output_text}")

                print(f"📊 Tool Output Received ({len(tool_output_text)} chars)")

                # Feed result back to history
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output_text
                })
            
            # --- SIMULATION FINAL ANSWER ---
            # Normally we would call the LLM again here to synthesize the answer.
            # Since we have no credits, we will just print the raw data.
            
            print("\n💬 LLM Reply (Raw Data Output):")
            print("Here is the data I found from the server:")
            print("-" * 40)
            print(tool_output_text)
            print("-" * 40)
            
            self.messages.append({"role": "assistant", "content": tool_output_text})
            return tool_output_text

        else:
            answer = initial_msg.content
            print(f"\n💬 LLM Reply:\n{answer}")
            self.messages.append({"role": "assistant", "content": answer})
            return answer

    async def cleanup(self):
        """Close connections properly."""
        await self.exit_stack.aclose()
        print("🔌 Connection closed.")

    async def log_conversation(self):
        os.makedirs("conversations", exist_ok=True)

        serializable_conversation = []

        for message in self.messages:
            try:
                serializable_message = {"role": message["role"], "content": []}

                # Handle both string and list content
                if isinstance(message["content"], str):
                    serializable_message["content"] = message["content"]
                elif isinstance(message["content"], list):
                    for content_item in message["content"]:
                        if hasattr(content_item, "to_dict"):
                            serializable_message["content"].append(
                                content_item.to_dict()
                            )
                        elif hasattr(content_item, "dict"):
                            serializable_message["content"].append(content_item.dict())
                        elif hasattr(content_item, "model_dump"):
                            serializable_message["content"].append(
                                content_item.model_dump()
                            )
                        else:
                            serializable_message["content"].append(content_item)

                serializable_conversation.append(serializable_message)
            except Exception as e:
                self.logger.error(f"Error serializing message: {e}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join("conversations", f"conversation_{timestamp}.json")

        try:
            with open(filepath, "w") as f:
                json.dump(serializable_conversation, f, indent=2, default=str)
                print(f"📝 Conversation logged to {filepath}")
        except Exception as e:
            self.logger.error(f"Error writing conversation to file: {str(e)}")

# --- Usage Example ---
async def main():
    # Initialize Client
    client = MCPClient(server_url="http://localhost:8000/mcp/sse")
    
    try:
        await client.connect()

        print("\n--- CTBA Analytics Assistant Ready (Type 'quit' to exit) ---")
        
        while True:
            user_input = input("\n👤 You: ")
            if user_input.lower() in ["quit", "exit"]:
                break
                
            await client.process_query(user_input)

    finally:
        await client.log_conversation()
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())