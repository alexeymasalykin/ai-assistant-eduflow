"""FastAPI application with lifespan, routers, and error handling.

App initialization:
1. Startup: connect database, initialize LLM, vector DB
2. Lifespan context manager (FastAPI 0.93+)
3. Register routers: Wappi, Bitrix, Admin
4. Global exception handler (no stack trace leaks)
5. Rate limiting via slowapi
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from rate_limiter import limiter

from config import settings
from integrations.database import Database
from integrations.bitrix_client import BitrixClient
from integrations.llm_client import LLMClient, create_llm_client
from integrations.vector_db import VectorDB
from integrations.wappi import WappiIncomingHandler, WappiOutgoingHandler
from agents.orchestrator import Orchestrator
from routers import wappi, bitrix, admin

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

# Global instances (populated in lifespan)
db: Database | None = None
llm_client: LLMClient | None = None
vector_db: VectorDB | None = None
bitrix_client: BitrixClient | None = None
wappi_incoming: WappiIncomingHandler | None = None
wappi_outgoing: WappiOutgoingHandler | None = None
orchestrator: Orchestrator | None = None
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan context manager for app startup/shutdown.

    Startup:
    1. Connect to PostgreSQL
    2. Initialize LLM client
    3. Initialize vector DB
    4. Initialize Bitrix client
    5. Initialize Wappi handlers
    6. Initialize orchestrator

    Shutdown:
    1. Close orchestrator
    2. Close Bitrix client
    3. Disconnect from database
    4. Close HTTP client
    """
    global db, llm_client, vector_db, bitrix_client
    global wappi_incoming, wappi_outgoing, orchestrator, http_client

    # ========================================================================
    # STARTUP
    # ========================================================================

    logger.info("app_startup_begin")

    try:
        # Initialize database
        logger.info("initializing_database", dsn=settings.postgres_dsn.split("@")[-1])
        db = Database(dsn=settings.postgres_dsn, min_size=2, max_size=10)
        await db.connect()

        # Initialize HTTP client (for Wappi API, LLM calls, etc.)
        logger.info("initializing_http_client")
        http_client = httpx.AsyncClient(timeout=15.0)

        # Initialize LLM client
        logger.info("initializing_llm_client", provider=settings.llm_provider.value)
        llm_client = create_llm_client(
            provider=settings.llm_provider.value,
            openai_api_key=settings.openai_api_key,
            yandex_api_key=settings.yandex_api_key,
            yandex_folder_id=settings.yandex_folder_id,
        )

        # Initialize vector DB
        logger.info("initializing_vector_db")
        vector_db = VectorDB(
            embeddings_api_key=settings.openai_embeddings_api_key,
            persist_dir="data/chroma_db",
        )

        # Index knowledge base (idempotent — safe to run on every startup)
        indexed = await vector_db.index_knowledge_base()
        logger.info("knowledge_base_indexed", documents=indexed)

        # Initialize Bitrix client
        logger.info("initializing_bitrix_client")
        bitrix_client = BitrixClient(
            webhook_url=settings.bitrix24_webhook_url,
        )

        # Initialize Wappi handlers
        logger.info("initializing_wappi_handlers")
        wappi_incoming = WappiIncomingHandler(db=db, bitrix=bitrix_client)
        wappi_outgoing = WappiOutgoingHandler(config=settings, http_client=http_client)

        # Initialize orchestrator
        logger.info("initializing_orchestrator")
        orchestrator = Orchestrator(
            llm=llm_client,
            bitrix=bitrix_client,
            vector_db=vector_db,
        )

        # Store in app state for dependency injection
        app.state.db = db
        app.state.llm_client = llm_client
        app.state.vector_db = vector_db
        app.state.bitrix_client = bitrix_client
        app.state.wappi_incoming = wappi_incoming
        app.state.wappi_outgoing = wappi_outgoing
        app.state.orchestrator = orchestrator
        app.state.http_client = http_client

        logger.info("app_startup_complete")

    except Exception as e:
        logger.critical("app_startup_failed", error=str(e))
        raise

    yield  # App runs here

    # ========================================================================
    # SHUTDOWN
    # ========================================================================

    logger.info("app_shutdown_begin")

    try:
        # Close resources
        if http_client:
            await http_client.aclose()
            logger.info("http_client_closed")

        if db:
            await db.disconnect()
            logger.info("database_closed")

        logger.info("app_shutdown_complete")

    except Exception as e:
        logger.error("app_shutdown_error", error=str(e))


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="EduFlow AI Assistant",
    description="AI-powered learning assistant for course management",
    version="1.0.0",
    lifespan=lifespan,
    debug=False,
)

# ============================================================================
# Rate Limiting
# ============================================================================

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ============================================================================
# Global Exception Handler
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Global exception handler - no stack traces leaked.

    Logs full error internally but returns safe response to client.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request.headers.get("X-Request-ID", "unknown"),
        },
    )


# ============================================================================
# Register Routers
# ============================================================================

app.include_router(wappi.router)
app.include_router(bitrix.router)
app.include_router(admin.router)


# ============================================================================
# Dependency Injection Helpers
# ============================================================================


async def get_database() -> Database:  # type: ignore[no-untyped-def]
    """Dependency: get database instance."""
    if not app.state.db:
        raise RuntimeError("Database not initialized")
    return app.state.db


async def get_orchestrator() -> Orchestrator:  # type: ignore[no-untyped-def]
    """Dependency: get orchestrator instance."""
    if not app.state.orchestrator:
        raise RuntimeError("Orchestrator not initialized")
    return app.state.orchestrator


async def get_wappi_incoming() -> WappiIncomingHandler:  # type: ignore[no-untyped-def]
    """Dependency: get Wappi incoming handler."""
    if not app.state.wappi_incoming:
        raise RuntimeError("Wappi incoming handler not initialized")
    return app.state.wappi_incoming


async def get_wappi_outgoing() -> WappiOutgoingHandler:  # type: ignore[no-untyped-def]
    """Dependency: get Wappi outgoing handler."""
    if not app.state.wappi_outgoing:
        raise RuntimeError("Wappi outgoing handler not initialized")
    return app.state.wappi_outgoing


async def get_bitrix_client() -> BitrixClient:  # type: ignore[no-untyped-def]
    """Dependency: get Bitrix client."""
    if not app.state.bitrix_client:
        raise RuntimeError("Bitrix client not initialized")
    return app.state.bitrix_client


# Register dependency providers with app
app.dependency_overrides = {
    Database: get_database,
    Orchestrator: get_orchestrator,
    WappiIncomingHandler: get_wappi_incoming,
    WappiOutgoingHandler: get_wappi_outgoing,
    BitrixClient: get_bitrix_client,
}
