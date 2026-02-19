# Codebasics Chat Buddy

An AI-powered lecture assistant that helps students understand course content. Built as "Peter Pandey" — a conversational instructor persona that answers questions strictly scoped to the lecture being viewed.

## Features

- **Lecture-scoped answering** — Uses RAG to answer from the current lecture's content, with awareness of previously covered lectures
- **Peter Pandey persona** — Friendly, Socratic instructor that teaches rather than just gives answers
- **Two chat modes** — "Teach Me" (guided hints, Socratic questioning) and "Direct" (straight answers)
- **Screenshot analysis** — Students can upload screenshots of code/errors for contextual help
- **Real-time streaming** — Server-Sent Events for natural typing-speed responses
- **Reference chips** — Shows which previous lectures are relevant when cross-referencing
- **Embeddable widget** — Drop an iframe into any webpage to add the chat assistant
- **Session-based chat history** — Persists within a browser tab, resets on navigation

## Architecture

```
Frontend (Next.js 16 + React 19 + TypeScript + Tailwind CSS 4)
    |
    | SSE streaming (/api/v2/chat/stream)
    |
Backend (FastAPI + Python)
    |
    +-- RAG Pipeline (dual-search: current lecture + previous lectures)
    +-- Qdrant Cloud (vector store, all-MiniLM-L6-v2 embeddings)
    +-- Groq API (llama-3.3-70b-versatile with model fallback chain)
```

**Dual mode:** Set `APP_MODE=rag` for production (Qdrant vector search) or `APP_MODE=csv` for local development (BM25 keyword search from CSV).

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.9+ and pip
- **Groq API Key** — [Get one free](https://console.groq.com/keys)
- **Qdrant Cloud** account (for RAG mode) — [qdrant.tech](https://qdrant.tech)

## Quick Start

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (Qdrant, MySQL, etc.)

# Run the server
python main.py
```

Backend runs at `http://localhost:8000` — API docs at `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (defaults work for local dev)
# Edit .env.local if backend URL differs from http://localhost:8000/api

# Run the dev server
npm run dev
```

Frontend runs at `http://localhost:3000`

### 3. Using the App

1. Navigate to **Courses** and select a course
2. Open a lecture — the chat widget appears on the right
3. Enter your Groq API key when prompted (inline in the chat panel)
4. Ask questions about the lecture content

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_MODE` | `csv` (local BM25) or `rag` (Qdrant vector search) | `csv` |
| `CSV_PATH` | Path to CSV data file (csv mode only) | `../sql_full.csv` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `DB_HOST` | MySQL host (for data ingestion) | — |
| `DB_PORT` | MySQL port | `3306` |
| `DB_NAME` | MySQL database name | — |
| `DB_USER` | MySQL user | — |
| `DB_PASSWORD` | MySQL password | — |
| `QDRANT_URL` | Qdrant Cloud endpoint | — |
| `QDRANT_API_KEY` | Qdrant Cloud API key | — |
| `EMBEDDING_MODEL` | Sentence-transformer model | `all-MiniLM-L6-v2` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000/api` |

## Embedding the Widget

The chat assistant can be embedded into any webpage via an iframe:

```html
<iframe
  src="https://your-domain.com/embed/LECTURE_ID"
  width="400"
  height="620"
  style="border:none; border-radius:12px;"
  allow="clipboard-write"
></iframe>
```

Replace `LECTURE_ID` with the numeric lecture ID. The embed route renders the chat panel without any navigation chrome.

Make sure the embedding domain is listed in `ALLOWED_ORIGINS` in the backend `.env`.

## Data Ingestion (RAG Mode)

To ingest course transcripts from MySQL into Qdrant:

```bash
cd backend

# Ingest a specific course
python scripts/ingest.py --course "Course Title"

# Or ingest from CSV
python scripts/ingest.py --from-csv
```

The ingestion pipeline:
1. Fetches transcripts from MySQL (or CSV)
2. Chunks text with overlap (500 chars, 100 overlap)
3. Generates embeddings via `all-MiniLM-L6-v2` (384 dimensions)
4. Upserts into Qdrant Cloud with metadata (course, chapter, lecture, order)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/courses` | List all courses |
| GET | `/api/courses/:courseId` | Course with chapters and lectures |
| GET | `/api/lectures/:lectureId` | Lecture detail with transcript |
| POST | `/api/llm/verify` | Verify Groq API key |
| POST | `/api/chat` | Chat (v1, CSV mode, non-streaming) |
| POST | `/api/v2/chat/stream` | Chat (v2, RAG mode, SSE streaming) |
| GET | `/api/v2/health` | RAG pipeline health check |
| GET | `/api/v2/rate-status` | Rate limit usage stats |
| GET | `/api/v2/cache-stats` | Cache hit/miss statistics |

## Project Structure

```
CB Chat Buddy/
├── backend/
│   ├── main.py                          # FastAPI entry point
│   ├── requirements.txt                 # Python dependencies
│   ├── .env.example                     # Environment template
│   └── app/
│       ├── api/routes.py                # All API endpoints (v1 + v2)
│       ├── models/schemas.py            # Pydantic request/response models
│       ├── services/
│       │   ├── llm.py                   # Groq LLM + Peter Pandey system prompt
│       │   ├── rag.py                   # RAG pipeline (dual-search, classify, stream)
│       │   ├── vector_store.py          # Qdrant wrapper
│       │   ├── embedding.py             # SentenceTransformer wrapper
│       │   ├── retrieval.py             # BM25 retriever (csv mode)
│       │   ├── cache.py                 # Response caching
│       │   └── rate_limiter.py          # Rate limiting
│       └── utils/
│           ├── csv_parser.py            # CSV + VTT transcript normalization
│           └── webvtt_parser.py         # WebVTT parser
├── frontend/
│   ├── app/
│   │   ├── courses/                     # Course catalog + lecture pages
│   │   ├── embed/[lectureId]/           # Embeddable widget route
│   │   └── profile/                     # Settings page
│   ├── components/ChatPanel.tsx         # Chat UI (streaming, modes, screenshots)
│   ├── lib/
│   │   ├── api.ts                       # Backend API client
│   │   └── storage.ts                   # localStorage/sessionStorage utilities
│   └── types/index.ts                   # TypeScript interfaces
├── backend/scripts/
│   ├── ingest.py                        # Qdrant data ingestion
│   └── export_db_to_csv.py             # MySQL to CSV export
└── embed-test.html                      # Widget embed test page
```

## LLM Model Chain

The app uses Groq with automatic model fallback:

| Priority | Model | Purpose |
|----------|-------|---------|
| Primary | `llama-3.3-70b-versatile` | Best persona adherence and reasoning |
| Fallback 1 | `llama-3.1-8b-instant` | Fast fallback when 70b is rate-limited |
| Fallback 2 | `gemma2-9b-it` | Final fallback |
| Vision | `meta-llama/llama-4-scout-17b-16e-instruct` | Screenshot analysis |
| Vision fallback | `meta-llama/llama-4-maverick-17b-128e-instruct` | Vision fallback |

## Deployment

### Backend (any Python host)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend (Vercel recommended)

```bash
cd frontend
npm run build
npm start
# Or: vercel deploy
```

Set `NEXT_PUBLIC_API_URL` to your backend's production URL.

## License

MIT
