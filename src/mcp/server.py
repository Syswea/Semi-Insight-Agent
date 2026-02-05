"""
MCP Server with DuckDuckGo Search Integration

This is a Model Context Protocol (MCP) server that exposes web search capabilities
to MCP-compatible clients (like Claude, Cursor, or custom LangGraph agents).

Key Design Decisions:
1. Uses FastMCP for stdio transport (Anthropic's official Python SDK)
2. Provides simple HTTP API for web applications
3. DuckDuckGo for free, no-API-key web search
4. Comprehensive logging at every step

Run with:
  - MCP stdio: python src/mcp/server.py
  - HTTP API:  python src/mcp/server.py --mode http

For Claude Desktop/Cursor: Use stdio mode.
For web apps: Use HTTP mode and call /api/search endpoint.
"""

import argparse
import json
import logging
import sys
import socket
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.tools import DuckDuckGoSearchRun

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [MCP] - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mcp.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str
    news: bool = False


class SearchResponse(BaseModel):
    result: str
    query: str
    mode: str


class MCPMessage(BaseModel):
    jsonrpc: str
    id: Any
    method: str
    params: dict | None = None


# FastAPI App for HTTP mode
app = FastAPI(
    title="MCP DuckDuckGo Search API",
    description="HTTP API wrapper for DuckDuckGo search",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DuckDuckGo Search
search_tool = DuckDuckGoSearchRun()


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "MCP DuckDuckGo Search API",
        "version": "1.0.0",
        "description": "HTTP API wrapper for DuckDuckGo search",
        "endpoints": {
            "GET /": "This info",
            "GET /health": "Health check",
            "POST /api/search": "Search the web (simple API)",
            "POST /api/search/news": "Search for news (simple API)",
            "POST /mcp": "MCP JSON-RPC protocol endpoint",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "MCP DuckDuckGo Search API"}


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search the web for information.

    Args:
        request: Search request with query

    Returns:
        Search results
    """
    logger.info(f"[HTTP API] Search request received: {request.query}")
    logger.info(f"[HTTP API] Mode: {'news' if request.news else 'web'}")

    try:
        query = request.query
        if request.news:
            query = f"{query} recent news"

        result = search_tool.invoke(query)
        logger.info(f"[HTTP API] Search returned {len(result)} characters")

        if not result or result.strip() == "":
            logger.info(f"[HTTP API] No results found for: {request.query}")
            result = f"No results found for: {request.query}"

        # Truncate if too long
        if len(result) > 2000:
            result = result[:2000] + "... [Results truncated]"
            logger.info(f"[HTTP API] Results truncated to 2000 characters")

        logger.info(f"[HTTP API] Search completed successfully")
        return SearchResponse(
            result=result,
            query=request.query,
            mode="news" if request.news else "web",
        )

    except Exception as e:
        logger.error(f"[HTTP API] Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/news", response_model=SearchResponse)
async def search_news(request: SearchRequest):
    """
    Search for recent news.

    This is a convenience endpoint equivalent to /api/search with news=True.
    """
    logger.info(f"[HTTP API] News search request received: {request.query}")

    request.news = True
    return await search(request)


@app.post("/mcp")
async def mcp_endpoint(request: MCPMessage):
    """
    MCP JSON-RPC protocol endpoint.

    Handles MCP tool calls from compatible clients.
    """
    logger.info(f"[MCP] Received JSON-RPC request: {request.method}")

    if request.method == "tools/list":
        # Return list of available tools
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "tools": [
                    {
                        "name": "web_search",
                        "description": "Search the web for information using DuckDuckGo",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "web_search_news",
                        "description": "Search for recent news using DuckDuckGo",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The news search query",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                ]
            },
        }

    elif request.method == "tools/call":
        # Handle tool call
        if request.params is None:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32602, "message": "Missing params"},
            }
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        logger.info(f"[MCP] Tool call: {tool_name}")
        logger.info(f"[MCP] Arguments: {arguments}")

        try:
            if tool_name == "web_search":
                query = arguments.get("query", "")
                logger.info(f"[MCP] Executing web_search: {query}")

                result = search_tool.invoke(query)
                logger.info(f"[MCP] Tool returned {len(result)} chars")

                if not result or result.strip() == "":
                    result = f"No results found for: {query}"

                if len(result) > 2000:
                    result = result[:2000] + "... [Truncated]"
                    logger.info(f"[MCP] Results truncated to 2000 chars")

                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result,
                            }
                        ]
                    },
                }

            elif tool_name == "web_search_news":
                query = arguments.get("query", "")
                news_query = f"{query} recent news"

                logger.info(f"[MCP] Executing web_search_news: {query}")

                result = search_tool.invoke(news_query)
                logger.info(f"[MCP] Tool returned {len(result)} chars")

                if not result or result.strip() == "":
                    result = f"No news found for: {query}"

                if len(result) > 2000:
                    result = result[:2000] + "... [Truncated]"
                    logger.info(f"[MCP] News truncated to 2000 chars")

                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result,
                            }
                        ]
                    },
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }

        except Exception as e:
            logger.error(f"[MCP] Tool execution failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32603, "message": str(e)},
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32600, "message": f"Unknown method: {request.method}"},
        }


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_stdio():
    """Run MCP Server with stdio transport (for Claude Desktop, Cursor, etc.)"""
    logger.info("=" * 60)
    logger.info("[MCP Server] Starting DuckDuckGo MCP Server")
    logger.info("[MCP Server] Transport: stdio")
    logger.info("[MCP Server] Available tools: web_search, web_search_news")
    logger.info("=" * 60)

    # Import FastMCP for stdio mode
    from fastmcp import FastMCP

    mcp = FastMCP("DuckDuckGoSearchServer")

    @mcp.tool
    def web_search(query: str) -> str:
        """
        Search the web for information using DuckDuckGo.

        Use this tool when you need real-time information not in your knowledge base.

        Args:
            query: The search query

        Returns:
            Search results from the web
        """
        logger.info(f"[MCP Tool] web_search called: {query}")

        try:
            result = search_tool.invoke(query)
            logger.info(f"[MCP Tool] Returned {len(result)} characters")

            if not result or result.strip() == "":
                return f"No results found for: {query}"

            if len(result) > 2000:
                result = result[:2000] + "... [Truncated]"
                logger.info(f"[MCP Tool] Results truncated to 2000 chars")

            logger.info(f"[MCP Tool] web_search completed successfully")
            return result
        except Exception as e:
            logger.error(f"[MCP Tool] web_search failed: {e}")
            return f"Search error: {str(e)}"

    @mcp.tool
    def web_search_news(query: str) -> str:
        """
        Search for recent news using DuckDuckGo.

        Args:
            query: The news search query

        Returns:
            Recent news articles
        """
        logger.info(f"[MCP Tool] web_search_news called: {query}")

        try:
            news_query = f"{query} recent news"
            result = search_tool.invoke(news_query)
            logger.info(f"[MCP Tool] Returned {len(result)} characters")

            if not result or result.strip() == "":
                return f"No news found for: {query}"

            if len(result) > 2000:
                result = result[:2000] + "... [Truncated]"
                logger.info(f"[MCP Tool] News truncated to 2000 chars")

            logger.info(f"[MCP Tool] web_search_news completed successfully")
            return result
        except Exception as e:
            logger.error(f"[MCP Tool] web_search_news failed: {e}")
            return f"News search error: {str(e)}"

    # Run with stdio transport
    mcp.run(transport="stdio")


def run_http(host: str = "0.0.0.0", port: int = 8000):
    """Run FastAPI server for HTTP access."""
    import uvicorn

    # Check if port is already in use
    if is_port_in_use(port):
        logger.warning(
            f"[MCP Server] Port {port} is already in use. Trying port {port + 1}..."
        )
        port = port + 1

    logger.info("=" * 60)
    logger.info("[MCP Server] Starting DuckDuckGo Search API")
    logger.info(f"[MCP Server] Transport: HTTP")
    logger.info(f"[MCP Server] Listening on http://{host}:{port}")
    logger.info("[MCP Server] Endpoints:")
    logger.info("  - GET  /           - Service info")
    logger.info("  - GET  /health    - Health check")
    logger.info("  - POST /api/search     - Web search (simple)")
    logger.info("  - POST /api/search/news - News search (simple)")
    logger.info("  - POST /mcp       - MCP JSON-RPC protocol")
    logger.info("=" * 60)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP DuckDuckGo Search Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (for Claude/Cursor) or http (for web apps)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP mode (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP mode (default: 8000)",
    )

    args = parser.parse_args()

    if args.mode == "stdio":
        run_stdio()
    else:
        run_http(args.host, args.port)
