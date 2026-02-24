# Codebasics Chat Buddy

> An AI-powered lecture assistant that lives right inside your course player — ask questions about any lecture and get instant, context-aware answers from **Peter Pandey**, your personal course instructor.

---

## 📦 Product Overview

**Codebasics Chat Buddy** is a RAG-powered (Retrieval-Augmented Generation) chat widget built for the [Codebasics](https://codebasics.io) learning platform. It embeds directly into the course player and allows students to have a real conversation about the lecture they're currently watching — without leaving the page.

The assistant is personified as **Peter Pandey** — a friendly, relatable instructor who has been through the same learning journey as the student. He adapts to how you learn: he can guide you Socratically (ask you questions, nudge you toward the answer) or give you a direct, concise answer when you just need the fix. He speaks both English and casual Hinglish, matching the natural communication style of most Indian developers.

### Key Features

| Feature | Description |
|---|---|
| 🎯 **Lecture-scoped RAG** | Answers are grounded strictly in the lecture transcript. Peter won't hallucinate or answer from the wrong lecture. |
| 🧠 **Dual Teaching Modes** | **Smart Friend** (Socratic, guided hints) or **Direct** (concise, opinionated answers). Student picks once, preference saved. |
| 🌐 **English + Hinglish** | Fully supports casual Hinglish (Hindi-English mix) — the natural language of Indian developers. |
| 📸 **Screenshot Analysis** | Students paste a screenshot of code, an error, or a chart and Peter analyzes it in context of the lecture. |
| ⚡ **Streaming Responses** | Server-Sent Events (SSE) deliver responses token-by-token, just like ChatGPT. No waiting for the full answer. |
| 🔗 **Cross-lecture References** | When Peter references a previous lecture, clickable reference chips appear so students can jump directly there. |
| 🔌 **Embeddable iframe Widget** | Drop one `<iframe>` line into any webpage to add the assistant to an external course player or LMS. |
| 💾 **Session History & Caching** | Chat history persists within a browser tab. Duplicate questions get cached answers instantly. |
| 🎙️ **Voice Input** | Students can dictate questions via browser speech recognition (English & Hinglish supported). |
| 🔄 **Model Fallback Chain** | 3-model fallback (llama-3.3-70b → llama-3.1-8b → gemma2-9b) ensures uptime even during Groq rate limits. |

---

## 👥 Who Uses This

Chat Buddy is built for **both** enrolled and non-enrolled Codebasics learners.

### 🎓 Bootcamp Users (Enrolled Students)
Students taking structured paid bootcamps (Data Analytics, ML, Python, Power BI, SQL, etc.):
- Want fast answers during a lecture without pausing to Google
- Learning at varying paces — some need Socratic guidance, others just want the direct answer
- Many are Indian professionals who naturally communicate in Hinglish
- Need the assistant to stay strictly on-topic — they're paying for course content, not generic ChatGPT answers

### 🆓 Non-Bootcamp Users (Free / Trial Learners)
Users exploring Codebasics free content or previewing a course before purchasing:
- Same core need: instant contextual answers without leaving the video
- Lower commitment threshold — first impression matters more here
- Chat Buddy serves as a product differentiator that nudges them toward enrollment

### Common Use Cases (Both Segments)
- *"What does this line of code actually do?"*
- *"Why is my output different from the instructor's?"*
- *"I missed the explanation at 12:30 — what was that concept?"*
- *"Give me a different real-world example of this"*
- *"Yaar, ye wala part samajh nahi aaya — explain kar"* *(Hinglish)*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│   Frontend: Next.js 16 + React 19 + TypeScript      │
│   Tailwind CSS 4  ·  SSE streaming  ·  localStorage │
└────────────────────┬────────────────────────────────┘
                     │  HTTP + Server-Sent Events
                     ▼
┌─────────────────────────────────────────────────────┐
│   Backend: FastAPI (Python)                         │
│                                                     │
│   ┌─────────────────────────────────────────────┐  │
│   │  RAG Pipeline                               │  │
│   │  1. Embed query (all-MiniLM-L6-v2, 384-dim) │  │
│   │  2. Dual-search Qdrant                      │  │
│   │     • Current lecture (strict scope)        │  │
│   │     • Previous lectures (cross-reference)   │  │
│   │  3. Classify: in-scope / future / off-topic │  │
│   │  4. Build labeled context for LLM           │  │
│   │  5. Stream response token-by-token via SSE  │  │
│   └──────────────┬──────────────────────────────┘  │
│                  │                                  │
│   ┌──────────────▼──────────────┐                  │
│   │  Groq LLM (model chain)     │                  │
│   │  llama-3.3-70b (primary)    │                  │
│   │  llama-3.1-8b  (fallback 1) │                  │
│   │  gemma2-9b     (fallback 2) │                  │
│   └─────────────────────────────┘                  │
└─────────────────────────────────────────────────────┘
                     │  Qdrant client (10s timeout)
                     ▼
┌─────────────────────────────────────────────────────┐
│   Qdrant Cloud (Vector DB)                          │
│   Collection: course_transcripts                    │
│   Embeddings: all-MiniLM-L6-v2  ·  384 dimensions  │
└─────────────────────────────────────────────────────┘
```

**Dual operation mode:**
- `APP_MODE=rag` → Full RAG with Qdrant vector search (production)
- `APP_MODE=csv` → BM25 keyword search from local CSV (development / demo — no Qdrant needed)

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16.1 (App Router), React 19, TypeScript 5, Tailwind CSS 4 |
| **Backend** | FastAPI 0.109, Python 3.9+, Uvicorn |
| **LLM** | Groq API — llama-3.3-70b-versatile (primary), automatic model fallback chain |
| **Vision LLM** | Groq — llama-4-scout-17b (screenshot analysis) |
| **Vector DB** | Qdrant Cloud |
| **Embeddings** | `sentence-transformers` — all-MiniLM-L6-v2 (384-dimensional) |
| **Streaming** | Server-Sent Events (SSE) via FastAPI `StreamingResponse` |
| **Data source** | MySQL (production ingest) · CSV (development fallback) |

---

## ⚙️ Setup Instructions

### Prerequisites

Before you start, make sure you have:

- **Node.js 18+** and npm — [nodejs.org](https://nodejs.org)
- **Python 3.9+** — [python.org](https://python.org)
- **Groq API Key** (free) — [console.groq.com/keys](https://console.groq.com/keys)
  > Each user supplies their own key in the chat UI. You don't need one for the server.
- **Qdrant Cloud** account (RAG mode only, free tier works) — [qdrant.tech](https://qdrant.tech)

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/Vishal14367/CB-Chat-Buddy.git
cd CB-Chat-Buddy
```

---

### Step 2 — Backend: install dependencies

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

---

### Step 3 — Backend: configure environment

```bash
cp .env.example .env
```

Open `backend/.env` and fill in your values:

```env
# Operation mode: "csv" (local dev, no Qdrant) or "rag" (production with vector search)
APP_MODE=csv

# Path to course transcript CSV (only used in csv mode)
CSV_PATH=../sql_full.csv

# CORS allowed origins — add your frontend URL
ALLOWED_ORIGINS=http://localhost:3000

# Discord community link (shown in off-topic / unanswerable responses)
DISCORD_URL=https://discord.gg/codebasics

# ── Required for RAG mode only ──────────────────────────────────────────────
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ── Required for data ingestion from MySQL only ─────────────────────────────
DB_HOST=your_mysql_host
DB_PORT=3306
DB_NAME=your_database_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

---

### Step 4 — Backend: run the server

```bash
# From the backend/ directory (with .venv activated)
python main.py

# Or, for production:
uvicorn main:app --host 0.0.0.0 --port 8000
```

- API server: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

---

### Step 5 — Frontend: install dependencies

```bash
cd ../frontend
npm install
```

---

### Step 6 — Frontend: configure environment

```bash
cp .env.local.example .env.local
```

`frontend/.env.local` — the default works for local development:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

---

### Step 7 — Frontend: run the dev server

```bash
npm run dev
```

Frontend runs at `http://localhost:3000`

---

### Step 8 — Open the app

1. Go to `http://localhost:3000/courses`
2. Select a course and open a lecture
3. The **Chat Buddy** panel appears on the right side
4. Enter your **Groq API key** when prompted (stored locally in your browser, never sent to the server)
5. Choose your mode — **Smart Friend** (guided learning) or **Direct** (quick answers)
6. Start chatting!

---

### (Optional) Step 9 — Ingest transcripts into Qdrant (RAG mode only)

Only needed if you're running `APP_MODE=rag` and want to populate your own Qdrant collection:

```bash
cd backend

# Ingest all courses from CSV
python scripts/ingest.py --from-csv

# Or ingest a specific course from MySQL
python scripts/ingest.py --course "Course Title Here"

# Batch ingest all courses with retry logic
python scripts/ingest_all.py
```

The ingestion pipeline:
1. Fetches lecture transcripts from MySQL or CSV
2. Normalizes WebVTT transcripts (strips timestamps, cue numbers)
3. Chunks text into ~500-char segments with 100-char overlap
4. Generates 384-dim embeddings with `all-MiniLM-L6-v2`
5. Upserts into Qdrant with metadata: `course_title`, `chapter_title`, `lecture_title`, `lecture_order`, `lecture_id`

---

## 🔌 Embedding the Widget

Add the chat assistant to any external webpage with a single iframe:

```html
<iframe
  src="https://your-domain.com/embed/LECTURE_ID"
  width="380"
  height="620"
  style="border: none; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.12);"
  allow="microphone"
  title="Codebasics Chat Buddy"
></iframe>
```

Replace `LECTURE_ID` with the numeric lecture ID (e.g. `1532`).

**Requirements:**
- The embedding domain must be listed in `ALLOWED_ORIGINS` in `backend/.env`
- The backend must be reachable from the embed page's network

**Test locally:** Open `http://localhost:3000/embed-demo.html` — a full mock course player with the widget embedded via iframe, with a lecture switcher.

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses` | List all courses |
| `GET` | `/api/courses/:courseId` | Course detail with chapters and lectures |
| `GET` | `/api/lectures/:lectureId` | Lecture metadata and transcript |
| `POST` | `/api/llm/verify` | Verify a Groq API key |
| `POST` | `/api/chat` | Chat v1 — CSV mode, non-streaming |
| `POST` | `/api/v2/chat/stream` | **Chat v2 — RAG mode, SSE streaming** (main endpoint) |
| `GET` | `/api/v2/health` | RAG pipeline + Qdrant health check |
| `GET` | `/api/v2/rate-status` | Current rate limit usage stats |
| `GET` | `/api/v2/cache-stats` | Cache hit/miss statistics |
| `GET` | `/health` | Basic backend health (always available) |

Full interactive docs: `http://localhost:8000/docs`

---

## 🗂️ Project Structure

```
CB-Chat-Buddy/
│
├── backend/
│   ├── main.py                      # FastAPI app entry point: CORS, middleware, startup
│   ├── requirements.txt             # Python dependencies
│   ├── .env.example                 # ← Copy this to .env
│   └── app/
│       ├── api/routes.py            # All API endpoints (v1 + v2)
│       ├── models/schemas.py        # Pydantic models with input validators
│       └── services/
│           ├── llm.py               # Peter Pandey system prompt + Groq streaming
│           ├── rag.py               # RAG pipeline: dual-search, classify, stream
│           ├── vector_store.py      # Qdrant client wrapper
│           ├── embedding.py         # SentenceTransformer wrapper
│           ├── retrieval.py         # BM25 keyword retriever (csv mode)
│           ├── cache.py             # Embedding + response caching
│           └── rate_limiter.py      # Per-key rate limiting
│       └── utils/
│           ├── csv_parser.py        # CSV parsing + lecture structure builder
│           └── webvtt_parser.py     # WebVTT transcript normalizer
│
├── backend/scripts/
│   ├── ingest.py                    # Main Qdrant ingestion script
│   ├── ingest_all.py                # Batch ingest all courses
│   ├── reingest_all.py              # Re-ingest with retry for Qdrant timeouts
│   └── export_db_to_csv.py          # MySQL → CSV export utility
│
├── frontend/
│   ├── app/
│   │   ├── courses/                 # Course catalog + lecture viewer pages
│   │   ├── embed/[lectureId]/       # Embeddable widget route (no nav chrome)
│   │   ├── profile/                 # Settings page (API key management)
│   │   ├── error.tsx                # Branded error boundary page
│   │   └── not-found.tsx            # Branded 404 page
│   ├── components/
│   │   └── ChatPanel.tsx            # Main chat UI (streaming, modes, voice, screenshots)
│   ├── lib/
│   │   ├── api.ts                   # Backend API client (with AbortController timeouts)
│   │   └── storage.ts               # localStorage / sessionStorage helpers
│   ├── public/
│   │   └── embed-demo.html          # Interactive iframe embed demo page
│   └── types/index.ts               # TypeScript interfaces
│
└── README.md
```

---

## 🤖 LLM Model Chain

| Priority | Model | Purpose |
|---|---|---|
| **Primary** | `llama-3.3-70b-versatile` | Best persona adherence, Hinglish, reasoning |
| **Fallback 1** | `llama-3.1-8b-instant` | Fast fallback during 70b rate limits |
| **Fallback 2** | `gemma2-9b-it` | Final fallback |
| **Vision** | `meta-llama/llama-4-scout-17b-16e-instruct` | Screenshot / image analysis |
| **Vision fallback** | `meta-llama/llama-4-maverick-17b-128e-instruct` | Vision fallback |

> **Why 70b matters as primary:** Smaller models (8b) cannot reliably follow the complex Peter Pandey system prompt. They break character, skip Socratic questioning, and revert to generic responses. The persona and teaching quality critically depend on the 70b model.

---

## 🚀 Deployment

### Backend (any Python WSGI host)

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Set all environment variables in your host's config. Ensure `ALLOWED_ORIGINS` includes your frontend's production URL.

**Recommended hosts:** Railway · Render · AWS EC2 · Google Cloud Run

### Frontend (Vercel recommended)

```bash
cd frontend
npm run build    # verify build passes locally first
```

Then deploy to Vercel and set:
```
NEXT_PUBLIC_API_URL = https://your-backend-domain.com/api
```

---

## ⚠️ Important Notes & Limitations

| Area | Note |
|---|---|
| **Groq API key** | Each user supplies their own free Groq key in the chat UI. There is **no server-side LLM key** — this means zero per-query LLM cost for Codebasics. |
| **Rate limits** | Groq's free tier has per-minute and daily token limits. Peter handles this gracefully with a clear user message and Discord CTA. |
| **Scope enforcement** | Peter only answers from lecture transcript content. General programming questions outside the transcript are redirected to Discord. |
| **Screenshot analysis** | Vision model requires separate Groq quota. Gracefully skipped if unavailable. |
| **RAG vs CSV mode** | `APP_MODE=csv` uses BM25 keyword search — lower quality. For production, always use `APP_MODE=rag` with Qdrant. |
| **Embedding model** | `all-MiniLM-L6-v2` is ~90 MB and downloaded on first run. Subsequent starts load from cache. |
| **Data privacy** | Question content is never logged — only `correlation_id` + `lecture_id`. Groq API keys are stored only in the user's browser `localStorage`, never on the server. |
| **CORS** | In production, explicitly set `ALLOWED_ORIGINS`. The default (`http://localhost:3000`) will block all production requests. |
| **History cap** | Chat history sent to the LLM is capped at 50 messages to prevent token overflow. |
| **Image upload cap** | Screenshot uploads are limited to 5 MB. |

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ for Codebasics learners.*
