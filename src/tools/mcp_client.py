"""
MCP Client Wrapper for LangGraph Integration

This module provides a way to call MCP Server tools from LangGraph.
It launches the MCP Server as a subprocess and communicates via stdio.

Architecture:
    LangGraph Node --> MCP Client --> MCP Server (subprocess) --> DuckDuckGo

This approach keeps:
1. MCP Server protocol-compliant (usable with Claude, Cursor, etc.)
2. LangGraph integration clean and testable
3. Separation of concerns (protocol vs business logic)
"""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for communicating with MCP Server via stdio transport.

    This implementation:
    1. Launches MCP Server as a subprocess
    2. Sends JSON-RPC messages over stdin/stdout
    3. Parses responses and returns results
    """

    def __init__(self, server_script: str = "src/mcp/server.py"):
        """
        Initialize MCP Client.

        Args:
            server_script: Path to MCP Server Python script
        """
        self.server_script = server_script
        self.process: subprocess.Popen | None = None
        self._connected = False

    def connect(self) -> bool:
        """
        Start MCP Server subprocess and establish connection.

        Returns:
            True if connection successful
        """
        try:
            self.process = subprocess.Popen(
                [sys.executable, self.server_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Initialize connection (MCP handshake)
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "langgraph-agent", "version": "1.0.0"},
                },
            }

            response = self._send_message(init_message)
            if response and "result" in response:
                self._connected = True
                logger.info("Connected to MCP Server")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to connect to MCP Server: {e}")
            return False

    def disconnect(self):
        """Close connection and terminate subprocess."""
        if self.process:
            self.process.stdin.close()
            self.process.wait()
            self._connected = False
            logger.info("Disconnected from MCP Server")

    def list_tools(self) -> list[dict]:
        """
        List available tools from MCP Server.

        Returns:
            List of tool definitions
        """
        if not self._connected:
            raise RuntimeError("Not connected to MCP Server")

        message = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = self._send_message(message)

        if response and "result" in response:
            return response["result"].get("tools", [])
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """
        Call a tool on the MCP Server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result as string
        """
        if not self._connected:
            raise RuntimeError("Not connected to MCP Server")

        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }

        response = self._send_message(message)

        if response and "result" in response:
            content = response["result"].get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", str(content))
            return str(content)
        elif "error" in response:
            return f"Tool error: {response['error']}"

        return "No result from tool"

    def _send_message(self, message: dict) -> dict | None:
        """
        Send JSON-RPC message and receive response.

        Args:
            message: JSON-RPC message dict

        Returns:
            Response dict or None
        """
        try:
            if not self.process or not self.process.stdin:
                raise RuntimeError("Process not running")

            # Send message
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line.strip())

            return None

        except Exception as e:
            logger.error(f"Message exchange failed: {e}")
            return None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def create_mcp_search_tool():
    """
    Factory function to create a search tool compatible with LangGraph.

    Returns:
        A tool function that can be used in LangGraph
    """
    client = MCPClient()

    def search(query: str) -> str:
        """
        Web search using MCP Server.

        Args:
            query: Search query

        Returns:
            Search results
        """
        try:
            if not client._connected:
                client.connect()

            result = client.call_tool("web_search", {"query": query})
            return result
        except Exception as e:
            logger.error(f"MCP search failed: {e}")
            return f"Search failed: {str(e)}"

    return search


if __name__ == "__main__":
    # Test MCP Client
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Testing MCP Client")
    print("=" * 60)

    try:
        with MCPClient("src/mcp/server.py") as client:
            if client._connected:
                print("\nConnected to MCP Server")

                # List tools
                tools = client.list_tools()
                print(f"\nAvailable tools: {[t['name'] for t in tools]}")

                # Call search tool
                print("\nTest: Search for NVIDIA")
                result = client.call_tool(
                    "web_search", {"query": "NVIDIA founded year"}
                )
                print(f"\nResult:\n{result[:500]}...")

    except Exception as e:
        print(f"Test failed: {e}")
