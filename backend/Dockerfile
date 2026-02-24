# ── Backend Dockerfile ─────────────────────────────────────────────────────────
# FastAPI + Python 3.11
# The embedding model (~90 MB) is pre-downloaded at build time so the container
# starts instantly with no cold-start delay on first request.

FROM python:3.11-slim

WORKDIR /app

# System deps: gcc needed for some numpy/pandas C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer — only re-runs if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformer embedding model into the image.
# This adds ~90 MB to the image but eliminates the cold-start download on first run.
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
print('Downloading all-MiniLM-L6-v2...'); \
SentenceTransformer('all-MiniLM-L6-v2'); \
print('Model ready.')"

# Copy application code (after deps so code changes don't bust the model layer)
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
