from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVERS = {
    "hotel-service": {"url": "http://localhost:8001/mcp", "transport": "streamable_http"},
    "flight-service": {"url": "http://localhost:8002/mcp", "transport": "streamable_http"},
}

_tools_cache = None


async def get_mcp_tools() -> dict:
    """Load MCP tools once, cache by name. Must be awaited from an async context."""
    global _tools_cache
    if _tools_cache is None:
        client = MultiServerMCPClient(MCP_SERVERS)
        tools = await client.get_tools()
        _tools_cache = {tool.name: tool for tool in tools}
    return _tools_cache