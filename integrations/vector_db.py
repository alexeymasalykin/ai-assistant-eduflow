from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb
import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger()

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")
CHROMA_DB_DIR = Path("data/chroma_db")
COLLECTION_NAME = "eduflow_knowledge"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


class VectorDB:
    """ChromaDB wrapper for RAG search."""

    def __init__(self, embeddings_api_key: str, persist_dir: str | None = None) -> None:
        db_path = persist_dir or str(CHROMA_DB_DIR)
        self._chroma_client = chromadb.PersistentClient(path=db_path)
        self._collection = self._chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._openai_client = AsyncOpenAI(api_key=embeddings_api_key)

    async def index_knowledge_base(self, kb_dir: Path | None = None) -> int:
        directory = kb_dir or KNOWLEDGE_BASE_DIR
        if not directory.exists():
            logger.warning("knowledge_base_dir_not_found", path=str(directory))
            return 0

        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []

        for md_file in sorted(directory.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            chunks = self._split_into_chunks(content)

            for i, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{md_file.name}:{i}".encode(), usedforsecurity=False).hexdigest()
                documents.append(chunk)
                ids.append(doc_id)
                metadatas.append({"source": md_file.name, "chunk_index": str(i)})

        if not documents:
            return 0

        embeddings = await self._get_embeddings(documents)

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info("knowledge_base_indexed", documents=len(documents))
        return len(documents)

    async def search(self, query: str, n_results: int = 3) -> list[str]:
        query_embedding = await self._get_embeddings([query])
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
        )
        documents = results.get("documents", [[]])[0]
        logger.info("rag_search", query_length=len(query), results=len(documents))
        return documents

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = await self._openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    @staticmethod
    def _split_into_chunks(text: str) -> list[str]:
        words = text.split()
        if len(words) <= CHUNK_SIZE:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(words):
            end = start + CHUNK_SIZE
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - CHUNK_OVERLAP
        return chunks
