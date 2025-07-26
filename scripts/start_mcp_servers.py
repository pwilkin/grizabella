import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, stdio_client

# Configuration
SERVERS = {
    "grizabella": {
        "transport": "stdio",
        "command": "poetry",
        "args": ["run", "python", "-m", "grizabella.mcp.server", "--db-path", "grizabella_mcp_db"],
    },
    "searxng-public": {
        "transport": "stdio",
        "command": "npx",
        "args": ["mcp-searxng-public"],
        "env": {
            "SEARXNG_BASE_URL": "https://searx.be;https://searx.tiekoetter.com;https://opnxng.com;https://searxng.world;https://searx.oloke.xyz;https://seek.fyi",
            "DEFAULT_LANGUAGE": "en"
        },
    },
    "fetch": {
        "transport": "stdio",
        "command": "npx",
        "args":  ["mcp-fetch-server"],
        "env": {
            "DEFAULT_LENGTH": "50000",
        },
    }
}

def create_client(server_name: str) -> StdioServerParameters:
    """Create a FastMCP client for the given server configuration."""
    print(f"Creating FastMCP client for {server_name}...")
    return StdioServerParameters(**SERVERS[server_name])
    

def create_clients() -> dict[str, StdioServerParameters]:
    clients = {}
    
    # Create clients for all servers
    for name in SERVERS.keys():
        clients[name] = create_client(name)
        
    return clients

class MCPClientManager:
    def __init__(self, params_by_name):
        self.params_by_name = params_by_name
        self.exit_stack = AsyncExitStack()
        self.sessions = {}

    async def open_all(self):
        # Open clients sequentially to avoid task group issues
        sessions = []
        session_names = []
        for name, params in self.params_by_name.items():
            try:
                read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                sessions.append(session)
                session_names.append(name)
            except Exception as e:
                print(f"Failed to open client for {name}: {e}")
                # Close any opened clients before re-raising
                await self.close()
                raise

        self.sessions = dict(zip(session_names, sessions))

    async def close(self):
        # Close in reverse order to avoid dependency issues
        # Use shielded approach to prevent cancellation issues
        try:
            await self.exit_stack.aclose()
        except RuntimeError as e:
            if "Attempted to exit cancel scope in a different task than it was entered in" in str(e):
                print("Warning: Cancel scope issue during cleanup, continuing anyway")
                # This is a known issue with the anyio library and stdio_client
                # We can't do much about it, so we'll continue
                pass
            else:
                raise
        except Exception as e:
            print(f"Error during cleanup: {e}")
            raise
