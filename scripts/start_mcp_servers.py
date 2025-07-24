from mcp import StdioServerParameters

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