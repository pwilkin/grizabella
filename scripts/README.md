# MCP Server Management Scripts

This directory contains scripts for managing Model Context Protocol (MCP) servers.

## start_mcp_servers.py

Starts the Grizabella, SearXNG, and Fetch MCP servers, registers their tools with LiteLLM, and verifies the registration.

### Usage:
```bash
python start_mcp_servers.py
```

### Features:
- Starts all three MCP servers as subprocesses
- Performs health checks on each server
- Registers tools with LiteLLM
- Provides verification of tool registration
- Graceful shutdown on keyboard interrupt

### Configuration:
Edit the `SERVERS` dictionary in the script to modify:
- Server commands
- Port numbers
- Health check endpoints