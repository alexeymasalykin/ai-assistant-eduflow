"""EduFlow MCP Server — exposes Knowledge Base and CRM tools.

Runs as a separate process from FastAPI. Supports stdio (default)
and SSE transport for network access.

Usage:
    python -m mcp_server.server              # stdio (for Claude Code / Cursor)
    python -m mcp_server.server --transport sse  # SSE (for Docker / network)
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from config import settings
from integrations.bitrix_client import BitrixClient
from integrations.vector_db import VectorDB
from mcp_server.tools_crm import register_crm_tools
from mcp_server.tools_kb import register_kb_tools

mcp = FastMCP(
    name="eduflow-assistant",
    description="EduFlow AI Assistant — knowledge base search and CRM access",
)

# Initialize shared dependencies
vector_db = VectorDB(
    embeddings_api_key=settings.openai_embeddings_api_key,
    persist_dir="data/chroma_db",
)
bitrix_client = BitrixClient(
    webhook_url=settings.bitrix24_webhook_url,
)

# Register tools
register_kb_tools(mcp, vector_db)
register_crm_tools(mcp, bitrix_client)

if __name__ == "__main__":
    mcp.run()
