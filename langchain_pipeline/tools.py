"""LangChain Tools for concept demonstration."""

from __future__ import annotations

from langchain_core.tools import Tool


def create_classify_tool(llm_client) -> Tool:
    from prompts.classifier import CLASSIFIER_SYSTEM_PROMPT

    async def classify(message: str) -> str:
        return await llm_client.generate(system_prompt=CLASSIFIER_SYSTEM_PROMPT, user_message=message)

    return Tool(
        name="classify_message",
        description="Classify student message into: course, platform, escalate",
        func=lambda x: x,
        coroutine=classify,
    )


def create_search_kb_tool(retriever) -> Tool:
    async def search(query: str) -> str:
        docs = await retriever.ainvoke(query)
        if not docs:
            return "No results found."
        return "\n".join(f"- {doc.page_content[:200]}" for doc in docs)

    return Tool(
        name="search_knowledge_base",
        description="Search EduFlow knowledge base for platform questions",
        func=lambda x: x,
        coroutine=search,
    )
