from __future__ import annotations

from pathlib import Path

import structlog
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = structlog.get_logger()

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")
CHROMA_DB_DIR = "data/chroma_db"
COLLECTION_NAME = "eduflow_knowledge_lc"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def build_retriever(
    embeddings_api_key: str,
    persist_dir: str = CHROMA_DB_DIR,
    k: int = 3,
):
    """Build LangChain retriever backed by ChromaDB.

    Uses the same embedding model (text-embedding-3-small) and search params
    as the original VectorDB implementation for consistent results.

    Args:
        embeddings_api_key: OpenAI API key for embeddings
        persist_dir: ChromaDB persistence directory
        k: Number of results to return (default: 3, same as original)
    """
    embeddings = OpenAIEmbeddings(
        api_key=embeddings_api_key,
        model="text-embedding-3-small",
    )
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return vectorstore.as_retriever(search_kwargs={"k": k})


def index_knowledge_base(
    kb_dir: Path = KNOWLEDGE_BASE_DIR,
    embeddings_api_key: str = "",
    persist_dir: str = CHROMA_DB_DIR,
) -> int:
    """Index knowledge base markdown files into ChromaDB via LangChain.

    Mirrors the original VectorDB.index_knowledge_base() logic:
    - Loads .md files from kb_dir via TextLoader
    - Splits into chunks (500 words, 50 overlap) via RecursiveCharacterTextSplitter
    - Indexes into ChromaDB with cosine similarity

    TextLoader chosen over UnstructuredMarkdownLoader to avoid heavy
    `unstructured` dependency — markdown files are simple and don't
    need structural parsing.

    Args:
        kb_dir: Directory with .md knowledge base files
        embeddings_api_key: OpenAI API key for embeddings
        persist_dir: ChromaDB persistence directory

    Returns:
        Number of document chunks indexed
    """
    from langchain_community.document_loaders import TextLoader

    md_files = sorted(kb_dir.glob("*.md"))
    if not md_files:
        logger.warning("langchain_kb_no_files", path=str(kb_dir))
        return 0

    all_docs = []
    for md_file in md_files:
        loader = TextLoader(str(md_file), encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = md_file.name
        all_docs.extend(docs)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda text: len(text.split()),
        is_separator_regex=False,
    )
    chunks = splitter.split_documents(all_docs)

    if not chunks:
        return 0

    embeddings = OpenAIEmbeddings(
        api_key=embeddings_api_key,
        model="text-embedding-3-small",
    )
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )

    logger.info("langchain_kb_indexed", documents=len(chunks))
    return len(chunks)
