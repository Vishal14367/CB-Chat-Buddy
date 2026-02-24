import os
import sys

# Windows OpenMP Fix (prevents crashes with multiple runtimes)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from app.api import routes
from app.utils.csv_parser import CSVDataSource
from app.services.llm import GroqLLMService

# Load environment variables
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ── Startup environment validation ─────────────────────────────────────────────

def _validate_env() -> None:
    """Fail fast at startup if required server-side environment variables are missing.

    NOTE: The Groq API key is user-provided per-request via the UI — it is NOT a
    server-side env var and is intentionally excluded from this check.
    """
    app_mode = os.getenv("APP_MODE", "csv")
    # In RAG mode, Qdrant URL is required on the server side
    required = ["QDRANT_URL"] if app_mode == "rag" else []
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        sys.exit(1)


_validate_env()


# ── Middleware: request body size limit ────────────────────────────────────────

class LimitRequestSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds MAX_BODY_BYTES (default 10 MB)."""

    MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large (max 10 MB)"})
        return await call_next(request)


# ── Middleware: security headers ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Course Buddy Bot API",
    description="Lecture-scoped AI chatbot for courses",
    version="0.2"
)

# Request size guard (must be before CORS to catch large pre-flight bodies)
app.add_middleware(LimitRequestSizeMiddleware)

# Security headers on all responses
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restrict to known origin(s) only; wildcard methods/headers removed
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── Data sources ───────────────────────────────────────────────────────────────

csv_path = os.getenv("CSV_PATH", "../sql.csv")
# Discord URL — must be set explicitly; no generic fallback that could mislead users
discord_url = os.getenv("DISCORD_URL") or "https://discord.gg/REPLACE_ME"

print(f"Loading CSV from: {csv_path}")
routes.csv_data = CSVDataSource(csv_path)
routes.llm_service = GroqLLMService(discord_url)
print(f"Loaded {len(routes.csv_data.lectures_by_id)} lectures")


# ── RAG pipeline (optional) ────────────────────────────────────────────────────

app_mode = os.getenv("APP_MODE", "csv")

if app_mode == "rag":
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStoreService
    from app.services.rag import RAGPipeline

    print("\nInitializing RAG pipeline...")

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    # qdrant_url is guaranteed non-None here (validated by _validate_env above)
    embedding_service = EmbeddingService(
        model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )
    # Eagerly load model in main thread to avoid partial initialization in async threads
    print("  Pre-loading embedding model...")
    embedding_service._ensure_model_loaded()

    vector_store = VectorStoreService(
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key
    )

    # Fail fast if Qdrant collection is unreachable in RAG mode
    if not vector_store.health_check():
        logger.error("Qdrant collection not found or unreachable. Run ingest.py first.")
        sys.exit(1)
    print("  Qdrant: connected")

    # Optional services
    rate_limiter = None
    cache_service = None

    try:
        from app.services.rate_limiter import RateLimiter
        rate_limiter = RateLimiter()
        print("  Rate limiter: enabled")
    except ImportError:
        pass

    try:
        from app.services.cache import CacheService
        cache_service = CacheService(embedding_service)
        print("  Cache service: enabled")
    except ImportError:
        pass

    routes.rag_pipeline = RAGPipeline(
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_service=routes.llm_service,
        rate_limiter=rate_limiter,
        cache_service=cache_service
    )

    print("RAG pipeline initialized")

else:
    print(f"\nRunning in CSV mode (APP_MODE={app_mode})")


@app.on_event("startup")
async def startup_event():
    """Pre-warm caches after the worker process starts (runs once per worker)."""
    if routes.rag_pipeline and routes.rag_pipeline.vector_store:
        print("  Pre-warming course catalog cache...")
        courses_list = routes.rag_pipeline.vector_store.get_all_courses()
        print(f"  Cached {len(courses_list)} courses")


# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(routes.router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "Course Buddy Bot API",
        "version": "0.2",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "lectures_loaded": len(routes.csv_data.lectures_by_id),
        "mode": app_mode,
        "rag_available": routes.rag_pipeline is not None
    }

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "127.0.0.1")
    use_reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=8000, reload=use_reload)
