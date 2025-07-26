import pytest
import tempfile
import shutil
from pathlib import Path
from contextlib import AsyncExitStack
from typing import AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'

@pytest.fixture(scope="module")
async def mcp_session() -> AsyncGenerator[ClientSession, None]:
    """
    Fixture to run the MCP server as a subprocess with an isolated, temporary
    database. It provides a ClientSession to interact with the server.
    This fixture is module-scoped to avoid server startup/shutdown for each test.
    """
    db_dir = tempfile.mkdtemp(prefix="grizabella_int_mcp_")
    db_path = Path(db_dir) / "integration_test_db"
    
    try:
        async with AsyncExitStack() as stack:
            server_args = ["-m", "grizabella.mcp.server", "--db-path", str(db_path)]
            params = StdioServerParameters(command="poetry", args=["run", "python"] + server_args)
            
            reader, writer = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(reader, writer))
            await session.initialize()
            
            yield session
    finally:
        if Path(db_dir).exists():
            shutil.rmtree(db_dir)