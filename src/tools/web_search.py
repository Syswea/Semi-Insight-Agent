"""
Web Search Tool Wrapper for LangGraph

This module provides a direct integration with DuckDuckGo search,
designed to work seamlessly with LangGraph's tool calling mechanism.

Design Rationale:
1. Uses LangChain's DuckDuckGo integration for simplicity
2. Directly callable from LangGraph nodes
3. Returns clean, formatted results for LLM consumption
4. Supports both direct and MCP proxy modes

For MCP-compatible clients (Claude, Cursor), use src/mcp/server.py instead.
"""

import logging
import sys
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [WebSearch] - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Wrapper class for DuckDuckGo web search.

    Provides a clean interface for LangGraph agents to access real-time
    information from the web.

    Supports two modes:
    - DIRECT: Uses DuckDuckGo SDK directly (fastest)
    - MCP_PROXY: Calls MCP Server via HTTP (protocol-compliant)
    """

    def __init__(self, use_mcp: bool = False, mcp_url: str = "http://localhost:8000"):
        """
        Initialize Web Search Tool.

        Args:
            use_mcp: Whether to use MCP Server proxy
            mcp_url: MCP Server URL when use_mcp is True
        """
        self.use_mcp = use_mcp
        self.mcp_url = mcp_url

        if not use_mcp:
            from langchain_community.tools import DuckDuckGoSearchRun

            self.search = DuckDuckGoSearchRun()
            logger.info(f"[WebSearch] Initialized in DIRECT mode")
        else:
            logger.info(f"[WebSearch] Initialized in MCP_PROXY mode, URL: {mcp_url}")

    def search_web(self, query: str) -> str:
        """
        Search the web for current information.

        Args:
            query: Search query string

        Returns:
            Search results with snippets
        """
        logger.info(f"[WebSearch] Searching web for: {query}")

        if self.use_mcp:
            return self._search_via_mcp(query)
        else:
            return self._search_direct(query)

    def search_news(self, query: str) -> str:
        """
        Search for recent news.

        Args:
            query: News search query

        Returns:
            Recent news articles
        """
        logger.info(f"[WebSearch] Searching news for: {query}")

        if self.use_mcp:
            return self._search_news_via_mcp(query)
        else:
            return self._search_news_direct(query)

    def _search_direct(self, query: str) -> str:
        """Direct DuckDuckGo search."""
        try:
            result = self.search.invoke(query)
            logger.info(f"[WebSearch] Direct search returned {len(result)} chars")

            if not result or result.strip() == "":
                return f"No results found for: {query}"

            if len(result) > 3000:
                result = result[:3000] + "\n\n[Results truncated]"
                logger.info(f"[WebSearch] Results truncated to 3000 chars")

            logger.info(f"[WebSearch] Direct search completed successfully")
            return result
        except Exception as e:
            logger.error(f"[WebSearch] Direct search failed: {e}")
            return f"Search error: {str(e)}"

    def _search_news_direct(self, query: str) -> str:
        """Direct DuckDuckGo news search."""
        try:
            news_query = f"{query} recent news"
            result = self.search.invoke(news_query)
            logger.info(f"[WebSearch] Direct news search returned {len(result)} chars")

            if not result or result.strip() == "":
                return f"No news found for: {query}"

            if len(result) > 3000:
                result = result[:3000] + "\n\n[News truncated]"
                logger.info(f"[WebSearch] News truncated to 3000 chars")

            logger.info(f"[WebSearch] Direct news search completed successfully")
            return result
        except Exception as e:
            logger.error(f"[WebSearch] Direct news search failed: {e}")
            return f"News search error: {str(e)}"

    def _search_via_mcp(self, query: str) -> str:
        """Search via MCP Server using JSON-RPC protocol."""
        import httpx

        mcp_url = f"{self.mcp_url}/mcp"
        logger.info(f"[WebSearch] Calling MCP Server at {mcp_url}")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    mcp_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "web_search", "arguments": {"query": query}},
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        content = data["result"].get("content", [])
                        if content:
                            result = content[0].get("text", str(content))
                            logger.info(
                                f"[WebSearch] MCP search returned {len(result)} chars"
                            )
                            logger.info(
                                f"[WebSearch] MCP search completed successfully"
                            )
                            return result
                    elif "error" in data:
                        logger.error(f"[WebSearch] MCP error: {data['error']}")
                        return f"MCP error: {data['error']}"

                logger.error(
                    f"[WebSearch] MCP request failed with status {response.status_code}"
                )
                return f"MCP request failed: {response.status_code}"

        except Exception as e:
            logger.error(f"[WebSearch] MCP call failed: {e}")
            return f"MCP call failed: {str(e)}"

    def _search_news_via_mcp(self, query: str) -> str:
        """News search via MCP Server using JSON-RPC protocol."""
        import httpx

        mcp_url = f"{self.mcp_url}/mcp"
        logger.info(f"[WebSearch] Calling MCP Server for news at {mcp_url}")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    mcp_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "web_search_news",
                            "arguments": {"query": query},
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        content = data["result"].get("content", [])
                        if content:
                            result = content[0].get("text", str(content))
                            logger.info(
                                f"[WebSearch] MCP news search returned {len(result)} chars"
                            )
                            logger.info(
                                f"[WebSearch] MCP news search completed successfully"
                            )
                            return result
                    elif "error" in data:
                        logger.error(f"[WebSearch] MCP news error: {data['error']}")
                        return f"MCP error: {data['error']}"

                logger.error(
                    f"[WebSearch] MCP news request failed with status {response.status_code}"
                )
                return f"MCP request failed: {response.status_code}"

        except Exception as e:
            logger.error(f"[WebSearch] MCP news call failed: {e}")
            return f"MCP call failed: {str(e)}"

    def _search_news_via_mcp(self, query: str) -> str:
        """News search via MCP Server."""
        import httpx

        logger.info(f"[WebSearch] Calling MCP Server for news at {self.mcp_url}")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self.mcp_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "web_search_news",
                            "arguments": {"query": query},
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        content = data["result"].get("content", [])
                        if content:
                            result = content[0].get("text", str(content))
                            logger.info(
                                f"[WebSearch] MCP news search returned {len(result)} chars"
                            )
                            logger.info(
                                f"[WebSearch] MCP news search completed successfully"
                            )
                            return result
                    elif "error" in data:
                        logger.error(f"[WebSearch] MCP news error: {data['error']}")
                        return f"MCP error: {data['error']}"

                logger.error(
                    f"[WebSearch] MCP news request failed with status {response.status_code}"
                )
                return f"MCP request failed: {response.status_code}"

        except Exception as e:
            logger.error(f"[WebSearch] MCP news call failed: {e}")
            return f"MCP call failed: {str(e)}"


# Singleton instance for LangGraph usage (MCP mode for protocol compliance)
web_search_tool = WebSearchTool(use_mcp=True, mcp_url="http://localhost:8002")


def web_search(query: str) -> str:
    """
    Convenience function for web search.

    This can be registered as a tool in LangGraph.

    Args:
        query: Search query

    Returns:
        Search results
    """
    return web_search_tool.search_web(query)


def web_news(query: str) -> str:
    """
    Convenience function for news search.

    Args:
        query: News query

    Returns:
        News results
    """
    return web_search_tool.search_news(query)


if __name__ == "__main__":
    # Test the tool
    print("=" * 60)
    print("Testing Web Search Tool")
    print("=" * 60)

    print("\nTest 1: Direct search mode")
    tool = WebSearchTool(use_mcp=False)
    result = tool.search_web("NVIDIA founded year headquarters")
    print(f"\nResult:\n{result[:500]}...")

    print("\n" + "=" * 60)
