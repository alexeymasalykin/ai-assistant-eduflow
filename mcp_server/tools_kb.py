"""MCP Tool: Knowledge Base search."""

from __future__ import annotations


def format_results(results: list[str]) -> str:
    """Format VectorDB search results for MCP tool response."""
    if not results:
        return "No results found in knowledge base."

    items = []
    for i, chunk in enumerate(results, start=1):
        truncated = chunk[:500] + "..." if len(chunk) > 500 else chunk
        items.append(f"{i}. {truncated}")
    return "\n\n".join(items)


def register_kb_tools(mcp, vector_db) -> None:
    """Register knowledge base tools with MCP server."""

    @mcp.tool()
    async def search_knowledge_base(query: str, n_results: int = 3) -> str:
        """Search EduFlow knowledge base for answers about the platform.

        Args:
            query: Student question about registration, payments,
                   certificates, video playback, or password reset
            n_results: Number of results to return (1-5)

        Returns:
            Relevant knowledge base excerpts with source file names
        """
        clamped = max(1, min(n_results, 5))
        results = await vector_db.search(query, n_results=clamped)
        return format_results(results)
