"""FastAPI application for the QA system."""

import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logger_config import setup_logging
from app.models import QuestionRequest, AnswerResponse, HealthResponse, IndexingStatusResponse
from app.retriever import get_retriever
from app.data_ingestion import get_ingestion_pipeline, get_indexing_state, run_background_indexing, print_sample_messages

# Setup logging
settings = get_settings()
logger = setup_logging(settings.log_level)

# Initialize Logfire (optional)
logfire_enabled = False
logfire = None
try:
    import logfire as logfire_module
    logfire = logfire_module
    
    if settings.logfire_token:
        try:
            logfire.configure(token=settings.logfire_token)
            logger.info("Logfire observability enabled")
            logfire_enabled = True
        except Exception as e:
            logger.warning(f"Failed to initialize Logfire: {e}. Continuing without observability.")
    else:
        logger.info("Logfire observability disabled (LOGFIRE_TOKEN not set)")
except ImportError:
    logger.info("Logfire not installed - continuing without observability")

# Wrapper for optional logfire instrumentation
def optional_instrument(name):
    """Decorator that only instruments if logfire is enabled."""
    def decorator(func):
        if logfire_enabled:
            return logfire.instrument(name)(func)
        return func
    return decorator

logger.info("=" * 80)
logger.info("AURORA QA SYSTEM - Starting up")
logger.info("=" * 80)

# Global state
app_state = {
    "indexing_task": None,
    "retriever": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    logger.info("Starting up Aurora QA System")

    try:
        # Initialize retriever
        logger.info("Initializing retriever components")
        retriever = get_retriever()
        app_state["retriever"] = retriever
        logger.info("Retriever initialized successfully")

        # Print sample messages to show what data is available
        print_sample_messages(count=10)

        # Start background indexing if enabled
        if settings.indexing_enabled:
            logger.info("Starting background indexing job")

            async def background_indexing():
                try:
                    await run_background_indexing()
                except Exception as e:
                    logger.error(f"Background indexing error: {e}")

            app_state["indexing_task"] = asyncio.create_task(background_indexing())
            logger.info("Background indexing task created")

        logger.info("Startup complete - ready to accept requests")

    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise

    yield  # App runs here

    logger.info("Shutting down Aurora QA System")

    try:
        # Cancel background tasks
        if app_state.get("indexing_task"):
            app_state["indexing_task"].cancel()
            logger.info("Indexing task cancelled")

        logger.info("Shutdown complete")

    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


# Create FastAPI app
app = FastAPI(
    title="Aurora QA System",
    description="Question-answering system for member data using RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Routes
# ============================================================================


@app.post("/ask", response_model=AnswerResponse)
@optional_instrument("ask_endpoint")
async def ask(request: QuestionRequest) -> AnswerResponse:
    """
    Ask a question and get an answer based on member data.

    Args:
        request: Question request with optional flags

    Returns:
        Answer response with optional sources and evaluations
    """
    logger.info(f"POST /ask - Question: {request.question[:50]}...")

    try:
        # Validate question
        if not request.question or len(request.question.strip()) == 0:
            logger.warning("Empty question received")
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Check if indexing is complete
        state = get_indexing_state()
        if not state["in_progress"] and state["indexed_messages"] == 0:
            logger.warning("Indexing not complete")
            raise HTTPException(
                status_code=503,
                detail="Indexing in progress. Please retry in a few seconds.",
            )

        # Get retriever and answer question
        retriever = app_state.get("retriever")
        if not retriever:
            logger.error("Retriever not initialized")
            raise HTTPException(status_code=500, detail="System not ready")

        response = await retriever.answer_question(request)

        logger.info(f"Question answered successfully (latency: {response.latency_ms:.1f}ms)")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /ask endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health", response_model=HealthResponse)
@optional_instrument("health_endpoint")
async def health() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status and indexing progress
    """
    logger.debug("GET /health")

    try:
        state = get_indexing_state()

        indexing_status = {
            "in_progress": state["in_progress"],
            "total_messages": state["total_messages"],
            "indexed_messages": state["indexed_messages"],
            "progress_percent": (state["indexed_messages"] / max(state["total_messages"], 1)) * 100,
            "last_indexed": state["last_indexed"].isoformat() if state["last_indexed"] else None,
            "last_error": state["last_error"],
        }

        overall_status = "healthy"
        if state["last_error"]:
            overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            indexing_status=indexing_status,
            timestamp=datetime.now(),
        )

    except Exception as e:
        logger.error(f"Error in /health endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Health check failed")


@app.post("/reindex")
@optional_instrument("reindex_endpoint")
async def reindex(force: bool = Query(False, description="Force re-indexing even if data exists")) -> dict:
    """
    Manually trigger re-indexing.
    
    Args:
        force: If True, re-index even if data already exists
    
    Returns:
        Status message
    """
    logger.info("POST /reindex - Manual re-indexing requested")
    
    try:
        from app.data_ingestion import get_ingestion_pipeline, should_index
        
        if not force:
            if not should_index():
                return {
                    "message": "Index already contains data. Use ?force=true to re-index anyway.",
                    "indexed_messages": get_indexing_state()["indexed_messages"]
                }
        
        pipeline = get_ingestion_pipeline()
        success = await pipeline.run_full_indexing()
        
        if success:
            return {
                "message": "Re-indexing completed successfully",
                "indexed_messages": get_indexing_state()["indexed_messages"]
            }
        else:
            raise HTTPException(status_code=500, detail="Re-indexing failed")
            
    except Exception as e:
        logger.error(f"Error in /reindex endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Re-indexing error: {str(e)}")


@app.get("/status", response_model=IndexingStatusResponse)
@optional_instrument("status_endpoint")
async def status() -> IndexingStatusResponse:
    """
    Get detailed indexing status.

    Returns:
        Detailed indexing status including retrieved vs missed messages
    """
    logger.debug("GET /status")

    try:
        state = get_indexing_state()

        progress = 0
        expected_total = state.get("expected_total_messages")
        fetched_messages = state.get("fetched_messages", state.get("indexed_messages", 0))
        missed_messages = state.get("missed_messages", 0)
        missed_ranges = state.get("missed_ranges", [])
        
        if expected_total and expected_total > 0:
            progress = (state["indexed_messages"] / expected_total) * 100
        elif state["total_messages"] > 0:
            progress = (state["indexed_messages"] / state["total_messages"]) * 100

        return IndexingStatusResponse(
            complete=not state["in_progress"] and state["indexed_messages"] > 0,
            progress_percent=progress,
            total_messages=state["indexed_messages"],  # Actually indexed
            indexed_messages=state["indexed_messages"],
            expected_total_messages=expected_total,
            fetched_messages=fetched_messages if fetched_messages > 0 else None,
            missed_messages=missed_messages if missed_messages > 0 else None,
            missed_ranges=missed_ranges if missed_ranges else None,
            last_indexed=state["last_indexed"],
            last_error=state["last_error"],
        )

    except Exception as e:
        logger.error(f"Error in /status endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Status check failed")


@app.get("/")
async def root():
    """Root endpoint."""
    logger.debug("GET /")
    return {
        "message": "Aurora QA System",
        "version": "1.0.0",
        "endpoints": {
            "ask": "POST /ask",
            "health": "GET /health",
            "status": "GET /status",
            "reindex": "POST /reindex?force=true (optional)",
            "docs": "GET /docs",
        },
    }


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "error": "Internal server error",
        "detail": str(exc),
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting uvicorn server")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())

