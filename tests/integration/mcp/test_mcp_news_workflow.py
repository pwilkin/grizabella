import os
from typing import cast
import pytest
import time
import psutil
from litellm import completion
from litellm.utils import get_response_string
from litellm.types.utils import ModelResponse, Choices
from grizabella.core.models import ObjectTypeDefinition, PropertyDefinition, PropertyDataType
from scripts.start_mcp_servers import create_clients, MCPClientManager

# Test configuration
TEST_DB_PATH = "test_mcp_news_db"
NEWS_OBJECT_TYPE = "NewsArticle"
MAX_TOKENS = 24000

# MCP client instances for reuse
MCP_CLIENTS = {}

@pytest.fixture(scope="module")
def news_object_type():
    return ObjectTypeDefinition(
        name=NEWS_OBJECT_TYPE,
        description="News article from web sources",
        properties=[
            PropertyDefinition(name="title", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="source", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="content", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="url", data_type=PropertyDataType.TEXT),
            PropertyDefinition(name="published_at", data_type=PropertyDataType.TEXT)
        ]
    )

async def get_tools_config(clients, sessions):
    """Return MCP tools configuration for LLM by reading from MCP servers"""
    print("Getting tools configuration from servers...")
    tools = []
    
    # Get tools from each client session
    for server_name, session in sessions.items():
        print(f"Getting tools from server: {server_name}")
        server_tools = await session.list_tools()
        print(f"Got {len(server_tools.tools)} tools from server: {server_name}")
        for tool in server_tools.tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": f"{server_name}:{tool.name}",
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            })
    print(f"Total tools collected: {len(tools)}")
    return tools

async def execute_tool_call(tool_call, sessions):
    """Execute a single tool call and return the result"""
    # Parse tool name to get server and tool
    tool_name_parts = tool_call.function.name.split(":", 1)
    if len(tool_name_parts) != 2:
        raise ValueError(f"Invalid tool name format: {tool_call.function.name}")
    
    server_name, tool_name = tool_name_parts
    if server_name not in sessions:
        raise ValueError(f"Unknown server: {server_name}")
    
    session = sessions[server_name]
    # Parse arguments from JSON string
    import json
    args = json.loads(tool_call.function.arguments)
    # Call the tool
    result = await session.call_tool(tool_name, args)
    return result

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY") or not os.getenv("OPENROUTER_MODEL"),
    reason="OpenRouter credentials not set"
)
async def test_news_workflow():
    # Create MCP clients using start_mcp_servers utility
    clients = create_clients()
    
    # Create persistent client sessions
    manager = None
    
    try:
        # Initialize client sessions
        print("Initializing client sessions...")
        manager = MCPClientManager(clients)
        await manager.open_all()
        print("All client sessions initialized successfully")
              
        # Set up LiteLLM model
        model = os.getenv("LMSTUDIO_MODEL")
        
        # System message guiding the LLM
        system_message = (
            "You are an AI assistant that uses external tools to complete tasks. "
            "Perform this workflow: "
            "1. Search for today's hottest news using searxng:search\n"
            "2. Fetch content of top 3 results using fetch:fetch_html\n"
            "3. Store each news as a NewsArticle object using grizabella:upsert_object\n"
            "4. Start new session and recall news using grizabella:find_objects\n"
            "5. Return the recalled news articles"
        )
        
        print("Getting tools configuration...")
        tools = await get_tools_config(clients, manager.sessions)
        print(f"Got {len(tools)} tools from servers")
        
        # Initialize message history
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Track total tool calls made
        total_tool_calls = 0
        max_iterations = 10  # Prevent infinite loops
        
        # Initialize response with first call before the loop
        response = completion(
            model=(str(model)) or "openai/auto",
            messages=messages,
            stream=False,
            tools=tools,
            tool_choice="auto",
            max_tokens=MAX_TOKENS,
            api_base="http://localhost:1234/v1",
            api_key="1234"
        )
        print(f"Initial LLM response: {response}")
        cast_response = cast(ModelResponse, response)
        try:
            content = cast(Choices, cast_response.choices)[0].message.content
            print(f"Initial response content: {content}")
        except (ValueError, IndexError, AttributeError) as e:
            print(f"Could not extract content from initial response: {e}")
        
        # Main workflow loop - continue until no more tool calls
        iteration = 0
        while iteration < max_iterations:
            cast_response = cast(ModelResponse, response)
            
            # Extract tool calls if present
            tool_calls = []
            try:
                if cast(Choices, cast_response.choices)[0].message.tool_calls:
                    tool_calls = cast(Choices, cast_response.choices)[0].message.tool_calls
            except (ValueError, IndexError, AttributeError) as e:
                print(f"Warning: Could not extract tool calls from response: {e}")
            
            # If no tool calls, we're done
            if not tool_calls:
                print(f"No tool calls in iteration {iteration}, breaking loop")
                break
                
            # Add assistant message with tool calls to history
            assistant_message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            }
            # Only add content if it exists
            try:
                content = cast(Choices, cast_response.choices)[0].message.content
                if content:
                    assistant_message["content"] = content
            except (ValueError, IndexError, AttributeError) as e:
                print(f"Warning: Could not extract content from response: {e}")
            messages.append(assistant_message)
            
            print(f"Iteration {iteration}: Got {len(tool_calls)} tool calls")
            for i, tool_call in enumerate(tool_calls):
                print(f"  Tool call {i+1}: {tool_call.function.name}")
                print(f"  Arguments: {tool_call.function.arguments}")
            
            # Execute each tool call and add results to message history
            for tool_call in tool_calls:
                total_tool_calls += 1
                
                # Execute the tool
                try:
                    print(f"Executing tool: {tool_call.function.name}")
                    result = await execute_tool_call(tool_call, manager.sessions)
                    print(f"Tool execution result: {result}")
                    
                    # Add tool response to message history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": str(result)
                    })
                    
                except Exception as e:
                    print(f"Error executing tool {tool_call.function.name}: {str(e)}")
                    # Add error message to message history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": f"Error: {str(e)}"
                    })
            
            # Get next response from LLM based on tool results
            response = completion(
                model=(str(model)) or "openai/auto",
                messages=messages,
                stream=False,
                tools=tools,
                tool_choice="auto",
                max_tokens=MAX_TOKENS,
                api_base="http://localhost:1234/v1",
                api_key="1234"
            )
            
            iteration += 1
        # Make final call to get response without tools if needed
        cast_response = cast(ModelResponse, response)
        tool_calls = []
        try:
            if cast(Choices, cast_response.choices)[0].message.tool_calls:
                tool_calls = cast(Choices, cast_response.choices)[0].message.tool_calls
        except (ValueError, IndexError, AttributeError):
            pass
            
        # If there are still tool calls, make one final call without tools to get response
        if tool_calls:
            response = completion(
                model=(str(model)) or "openai/auto",
                messages=messages,
                stream=False,
                tools=[],  # No tools to prevent further tool calls
                tool_choice="none",
                max_tokens=MAX_TOKENS,
                api_base="http://localhost:1234/v1",
                api_key="1234"
            )
        
        final_response = get_response_string(cast(ModelResponse, response))
        # Verify we have executed tool calls
        assert total_tool_calls > 0, "No tool calls were made"
        assert total_tool_calls >= 5, "Insufficient tool calls made"
        
        # Verify final response contains news
        assert isinstance(final_response, str), "Response content should be a string"
        assert len(final_response) > 0, "Response content should not be empty"
        assert "news" in final_response.lower(), "No news in final response"
        assert len(final_response) > 100, "Insufficient recall response"
        
        print(f"LLM successfully completed workflow:\n{final_response}")
    
    finally:
        # Cleanup - close client sessions
        if manager:
            await manager.close()
        
        # Cleanup - terminate any child processes
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
                print(f"Terminated child process: {child.pid} ({child.name()})")
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                print(f"Error terminating process {child.pid}: {e}")
                
        # Remove test database with retries
        if os.path.exists(TEST_DB_PATH):
            # Allow time for processes to terminate
            time.sleep(2)
            
            # Retry removal to handle locked files
            for attempt in range(5):
                try:
                    # Remove all files in the database directory
                    for root, dirs, files in os.walk(TEST_DB_PATH):
                        for file in files:
                            file_path = os.path.join(root, file)
                            os.remove(file_path)
                            print(f"Removed file: {file_path}")
                    
                    # Remove all subdirectories
                    for root, dirs, files in os.walk(TEST_DB_PATH, topdown=False):
                        for dir in dirs:
                            dir_path = os.path.join(root, dir)
                            os.rmdir(dir_path)
                            print(f"Removed directory: {dir_path}")
                    
                    # Finally remove the main database directory
                    os.rmdir(TEST_DB_PATH)
                    print(f"Removed database directory: {TEST_DB_PATH}")
                    break
                except Exception as e:
                    print(f"Error removing database (attempt {attempt+1}): {e}")
                    time.sleep(1)
            else:
                print("Failed to remove database directory after 5 attempts")

if __name__ == "__main__":
    pytest.main([__file__])