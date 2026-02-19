import os

# Windows OpenMP Fix (prevents crashes with multiple runtimes)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api import routes
from app.utils.csv_parser import CSVDataSource
from app.services.llm import GroqLLMService

# Load environment variables
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Course Buddy Bot API",
    description="Lecture-scoped AI chatbot for courses",
    version="0.2"
)

# CORS settings
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data sources
csv_path = os.getenv("CSV_PATH", "../sql.csv")
discord_url = os.getenv("DISCORD_URL", "https://discord.com")

print(f"Loading CSV from: {csv_path}")
routes.csv_data = CSVDataSource(csv_path)
routes.llm_service = GroqLLMService(discord_url)
print(f"Loaded {len(routes.csv_data.lectures_by_id)} lectures")

# Initialize RAG pipeline if in RAG mode
app_mode = os.getenv("APP_MODE", "csv")

if app_mode == "rag":
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStoreService
    from app.services.rag import RAGPipeline

    print("\nInitializing RAG pipeline...")

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        print("WARNING: QDRANT_URL not set. RAG pipeline will not be available.")
    else:
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

        # Optional services (initialized in later phases)
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

        if vector_store.health_check():
            print("  Qdrant: connected")
        else:
            print("  WARNING: Qdrant collection not found. Run ingest.py first.")

        print("RAG pipeline initialized")
else:
    print(f"\nRunning in CSV mode (APP_MODE={app_mode})")

# Include API routes
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
