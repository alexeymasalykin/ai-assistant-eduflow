from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from langchain_pipeline.rag import build_retriever, index_knowledge_base


class TestBuildRetriever:
    def test_returns_retriever(self) -> None:
        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings"):
            mock_chroma.return_value = MagicMock()
            mock_chroma.return_value.as_retriever.return_value = MagicMock()

            retriever = build_retriever(embeddings_api_key="test-key", persist_dir="data/chroma_db")
            assert retriever is not None
            mock_chroma.return_value.as_retriever.assert_called_once_with(search_kwargs={"k": 3})

    def test_uses_correct_embedding_model(self) -> None:
        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings") as mock_embeddings:
            mock_chroma.return_value = MagicMock()
            mock_chroma.return_value.as_retriever.return_value = MagicMock()

            build_retriever(embeddings_api_key="test-key", persist_dir="data/chroma_db")
            mock_embeddings.assert_called_once_with(api_key="test-key", model="text-embedding-3-small")


class TestIndexKnowledgeBase:
    def test_index_from_directory(self, tmp_path: Path) -> None:
        (tmp_path / "test1.md").write_text("First document content about registration.")
        (tmp_path / "test2.md").write_text("Second document content about payments.")

        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings"):
            mock_vs = MagicMock()
            mock_chroma.from_documents.return_value = mock_vs

            result = index_knowledge_base(
                kb_dir=tmp_path, embeddings_api_key="test-key", persist_dir=str(tmp_path / "chroma"),
            )
            assert result > 0
            mock_chroma.from_documents.assert_called_once()

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        with patch("langchain_pipeline.rag.Chroma"), \
             patch("langchain_pipeline.rag.OpenAIEmbeddings"):
            result = index_knowledge_base(
                kb_dir=tmp_path, embeddings_api_key="test-key", persist_dir=str(tmp_path / "chroma"),
            )
            assert result == 0
