# Course Buddy Bot - Backend

FastAPI backend with lecture-scoped AI chatbot.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env if needed
```

3. Run the server:
```bash
python main.py
```

The API will be available at http://localhost:8000

## API Documentation

Interactive docs: http://localhost:8000/docs

### Endpoints

- `GET /api/courses` - List all courses
- `GET /api/courses/{courseId}` - Get course with chapters and lectures
- `GET /api/lectures/{lectureId}` - Get lecture detail with transcript
- `POST /api/llm/verify` - Verify Groq API key
- `POST /api/chat` - Chat with lecture-scoped context (strict)

## Key Features

- **Lecture-Only Answering**: Uses ONLY the transcript from the requested lecture
- **VTT Normalization**: Strips WEBVTT headers, timestamps, cue numbers
- **BM25 Retrieval**: Keyword-based chunking and ranking
- **Strict Grounding**: LLM prompt enforces no external knowledge
- **Not-Answerable Detection**: Returns Discord CTA when answer not in transcript
