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
        async def open_one(name, params):
            read, write = await self.exit_stack.enter_async_context(stdio_client(params))
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            return session

        sessions = await asyncio.gather(
            *(open_one(name, params) for name, params in self.params_by_name.items())
        )
        self.sessions = dict(zip(self.params_by_name.keys(), sessions))

    async def close(self):
        await self.exit_stack.aclose()
