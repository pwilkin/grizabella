"""
Integration test for MCP server using the official MCP client library
"""
import asyncio
import unittest
import subprocess
import time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TEST_DB_PATH = "test_mcp_client_db"

class TestMCPClientRequests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start the MCP server in a separate process
        cls.server_process = subprocess.Popen(
            ["python", "-m", "grizabella.mcp.server", "--db-path", TEST_DB_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Give server time to start
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        # Stop the server
        cls.server_process.terminate()
        cls.server_process.wait()
        # Clean up test database
        test_db = Path(TEST_DB_PATH)
        if test_db.exists():
            for f in test_db.glob("*"):
                f.unlink()
            test_db.rmdir()

    async def run_client_test(self):
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "grizabella.mcp.server", "--db-path", TEST_DB_PATH],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()

                # Call the create_object_type tool
                result = await session.call_tool(
                    "create_object_type",
                    arguments={
                        "object_type_def": {
                            "name": "CityState",
                            "description": "A city-state with hierarchical structure",
                            "properties": [
                                {"name": "name", "data_type": "TEXT", "is_indexed": True, "is_nullable": False},
                                {"name": "structure", "data_type": "TEXT", "is_indexed": True, "is_nullable": False},
                                {"name": "population", "data_type": "INTEGER", "is_nullable": True},
                                {"name": "government_type", "data_type": "TEXT", "is_nullable": True}
                            ]
                        }
                    }
                )
                return result

    def test_create_object_type(self):
        # Run the async test
        result = asyncio.run(self.run_client_test())
        # Verify successful response (CallToolResult with text content 'null')
        self.assertFalse(result.isError)
        self.assertEqual(len(result.content), 1)
        self.assertEqual(result.content[0].type, "text")
        if result.content[0].type == "text":
            self.assertEqual(result.content[0].text, "null")

if __name__ == "__main__":
    unittest.main()