import json
import logging
import re

from fastapi import APIRouter, HTTPException, Depends, Path
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    Course, CourseDetail, LectureDetail,
    ChatRequest, ChatResponse,
    VerifyKeyRequest, VerifyKeyResponse,
    RAGChatRequest, RAGChatResponse, ReferenceItem
)
from app.utils.csv_parser import CSVDataSource
from app.services.retrieval import LectureRetriever
from app.services.llm import GroqLLMService
from app.config.course_catalog import get_course_metadata
from typing import List, Optional
import os

logger = logging.getLogger(__name__)

# Safe pattern for path parameters (alphanumeric, hyphens, underscores only)
_SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')

router = APIRouter()

# Global instances (initialized in main.py)
csv_data: CSVDataSource = None
llm_service: GroqLLMService = None
rag_pipeline = None  # Initialized in main.py when APP_MODE=rag


def get_csv_data() -> CSVDataSource:
    """Dependency to get CSV data source."""
    if csv_data is None:
        raise HTTPException(status_code=500, detail="Data source not initialized")
    return csv_data


def get_llm_service() -> GroqLLMService:
    """Dependency to get LLM service."""
    if llm_service is None:
        raise HTTPException(status_code=500, detail="LLM service not initialized")
    return llm_service


@router.get("/courses", response_model=List[Course])
async def get_courses(data: CSVDataSource = Depends(get_csv_data)):
    """Get list of all courses.

    Always prefer CSV / metadata-JSON data (which has all 57 courses with
    correct chapter overrides).  Fall back to Qdrant only when CSV data is
    completely empty (should not happen in practice).
    """
    courses = data.get_all_courses()
    if not courses and rag_pipeline and rag_pipeline.vector_store:
        courses = rag_pipeline.vector_store.get_all_courses()
    for course in courses:
        course["category"] = get_course_metadata(course["course_title"])
    return courses


@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course_detail(course_id: str, data: CSVDataSource = Depends(get_csv_data)):
    """Get course with chapters and lectures.

    Prefer CSV / metadata-JSON (has chapter overrides applied).  Fall back to
    Qdrant only when CSV does not have the requested course.
    """
    if not _SAFE_ID_PATTERN.match(course_id):
        raise HTTPException(status_code=400, detail="Invalid course_id format")

    # Prefer CSV / metadata source (chapter overrides applied here)
    course = data.get_course_detail(course_id)
    if course:
        return course

    # Fall back to Qdrant if available
    if rag_pipeline and rag_pipeline.vector_store:
        course_title = rag_pipeline.vector_store.resolve_course_title(course_id)
        if course_title:
            course = rag_pipeline.vector_store.get_course_detail(course_title)
            if course:
                return course

    raise HTTPException(status_code=404, detail="Course not found")


@router.get("/lectures/{lecture_id}", response_model=LectureDetail)
async def get_lecture_detail(lecture_id: str, data: CSVDataSource = Depends(get_csv_data)):
    """Get lecture metadata and transcript. Uses Qdrant in RAG mode."""
    if not _SAFE_ID_PATTERN.match(lecture_id):
        raise HTTPException(status_code=400, detail="Invalid lecture_id format")
    if rag_pipeline and rag_pipeline.vector_store:
        lecture = rag_pipeline.vector_store.get_lecture_detail(lecture_id)
        if lecture:
            return lecture

    lecture = data.get_lecture_detail(lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


@router.post("/llm/verify", response_model=VerifyKeyResponse)
async def verify_groq_key(
    request: VerifyKeyRequest,
    service: GroqLLMService = Depends(get_llm_service)
):
    """Verify Groq API key."""
    is_valid, message = service.verify_api_key(request.apiKey)
    return VerifyKeyResponse(ok=is_valid, message=message)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    data: CSVDataSource = Depends(get_csv_data),
    service: GroqLLMService = Depends(get_llm_service)
):
    """
    Chat endpoint with strict lecture-only answering.
    CRITICAL: Uses ONLY the transcript from the requested lectureId.
    """
    # Validate message length
    if len(request.message) > 1000:
        raise HTTPException(status_code=400, detail="Message too long (max 1000 characters)")
    
    # Get lecture data (SINGLE LECTURE ONLY)
    lecture = data.get_lecture_detail(request.lectureId)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    
    transcript = lecture.get('transcript', '')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not available for this lecture")
    
    # Build retriever for THIS LECTURE ONLY
    retriever = LectureRetriever(transcript, chunk_size=300, threshold=0.0)

    # Retrieve relevant chunks — always send to LLM, let it decide answerability
    chunks, _ = retriever.retrieve(request.message, top_k=3)

    # If transcript produced no chunks at all, it's truly empty
    if not chunks:
        return ChatResponse(
            message=f"I don't see that topic covered in this particular lecture. It might come up in the next one — keep going!\n\nIf you're stuck on something specific, feel free to ask on our [Discord community]({service.discord_url}) where other learners and support folks can help out! 💪",
            isNotAnswerable=True,
            discordUrl=service.discord_url
        )
    
    # Generate response using Groq
    try:
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        response_text = service.generate_response(
            api_key=request.apiKey,
            query=request.message,
            context_chunks=chunks,
            course_title=lecture.get('course_title', 'this course'),
            chapter_title=lecture.get('chapter_title', 'this chapter'),
            lecture_title=lecture.get('lecture_title', 'this lecture'),
            history=history
        )
        
        return ChatResponse(
            message=response_text,
            isNotAnswerable=False
        )
    
    except Exception as e:
        # Handle LLM errors — log internally, return sanitized message to client
        error_msg = str(e)
        logger.error(f"Chat endpoint error: {error_msg}")
        if "rate limit" in error_msg.lower():
            return ChatResponse(
                message="Oops, looks like you've hit the rate limit! If this is a per-minute limit, just wait about **60 seconds** and try again. If you've used up your daily tokens, they reset at **midnight UTC** (every 24 hours). In the meantime, our [Discord community](" + service.discord_url + ") is always there to help!",
                isNotAnswerable=True,
                discordUrl=service.discord_url
            )
        elif "invalid api key" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        else:
            raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# --- RAG v2 Endpoints ---

def get_rag_pipeline():
    """Dependency to get RAG pipeline."""
    if rag_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not initialized. Set APP_MODE=rag in .env"
        )
    return rag_pipeline


@router.post("/v2/chat/stream")
async def chat_v2_stream(request: RAGChatRequest):
    """SSE streaming version of chat. Uses RAG pipeline when available, falls back to CSV."""
    history = [{"role": msg.role, "content": msg.content} for msg in request.history]

    # Resolve chapter/lecture titles
    chapter_title = ""
    lecture_title = ""
    lecture_detail = None
    if csv_data:
        lecture_detail = csv_data.get_lecture_detail(request.lectureId)
    if not lecture_detail and rag_pipeline and rag_pipeline.vector_store:
        lecture_detail = rag_pipeline.vector_store.get_lecture_detail(request.lectureId)
    if lecture_detail:
        chapter_title = lecture_detail.get('chapter_title', '')
        lecture_title = lecture_detail.get('lecture_title', '')

    # If screenshot is provided, analyze it first
    image_context = ""
    if request.imageBase64:
        try:
            image_context = llm_service.analyze_image(
                api_key=request.apiKey,
                image_base64=request.imageBase64,
                question=request.message
            )
        except Exception as e:
            image_context = f"(Screenshot analysis failed: {str(e)[:100]})"

    # --- RAG mode: use full pipeline ---
    if rag_pipeline is not None:
        async def rag_event_generator():
            try:
                async for event in rag_pipeline.process_question_stream(
                    question=request.message,
                    course_title=request.courseTitle,
                    current_lecture_order=request.currentLectureOrder,
                    lecture_id=request.lectureId,
                    api_key=request.apiKey,
                    history=history,
                    chapter_title=chapter_title,
                    lecture_title=lecture_title,
                    teaching_mode=request.teachingMode or "fix",
                    response_style=request.responseStyle or "casual",
                    hint_stage=request.hintStage or 1,
                    image_context=image_context
                ):
                    yield event
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred. Please try again.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"

        return StreamingResponse(
            rag_event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )

    # --- CSV fallback: stream from single-lecture transcript ---
    if not lecture_detail:
        raise HTTPException(status_code=404, detail="Lecture not found")

    transcript = lecture_detail.get('transcript', '')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not available for this lecture")

    retriever = LectureRetriever(transcript, chunk_size=300, threshold=0.0)
    chunks, _ = retriever.retrieve(request.message, top_k=3)
    context_string = "\n\n".join(chunks) if chunks else ""

    async def csv_event_generator():
        try:
            if not chunks:
                msg = "I don't see that topic covered in this particular lecture. It might come up in the next one — keep going!"
                yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'out_of_scope'})}\n\n"
                return

            async for token in llm_service.generate_response_stream(
                api_key=request.apiKey,
                query=request.message,
                context_string=context_string,
                course_title=lecture_detail.get('course_title', 'this course'),
                chapter_title=chapter_title or 'this chapter',
                lecture_title=lecture_title or 'this lecture',
                history=history,
                teaching_mode=request.teachingMode or "fix",
                response_style=request.responseStyle or "casual",
                hint_stage=request.hintStage or 1,
            ):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'in_scope'})}\n\n"
        except Exception as e:
            logger.error(f"CSV stream error: {e}")
            error_msg = str(e)
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Rate limit hit. Wait about 60 seconds and try again.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'rate_limited'})}\n\n"
            elif "invalid api key" in error_msg.lower() or "401" in error_msg:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Invalid API key. Please update it in Settings.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred. Please try again.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"

    return StreamingResponse(
        csv_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.get("/v2/health")
async def rag_health():
    """Check RAG pipeline health."""
    if rag_pipeline is None:
        return {"status": "csv_mode", "rag_available": False}

    qdrant_ok = rag_pipeline.vector_store.health_check()
    return {
        "status": "ok" if qdrant_ok else "degraded",
        "rag_available": True,
        "qdrant_connected": qdrant_ok
    }


@router.get("/v2/rate-status")
async def get_rate_status():
    """Get current rate limit usage stats."""
    if rag_pipeline is None or rag_pipeline.rate_limiter is None:
        return {"status": "not_available"}
    return rag_pipeline.rate_limiter.get_status()


@router.get("/v2/cache-stats")
async def get_cache_stats():
    """Get cache hit/miss statistics."""
    if rag_pipeline is None or rag_pipeline.cache is None:
        return {"status": "not_available"}
    return rag_pipeline.cache.get_stats()
