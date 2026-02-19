import json

from fastapi import APIRouter, HTTPException, Depends
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
from typing import List, Optional
import os

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
    """Get list of all courses. Uses Qdrant in RAG mode, CSV otherwise."""
    if rag_pipeline and rag_pipeline.vector_store:
        return rag_pipeline.vector_store.get_all_courses()
    return data.get_all_courses()


@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course_detail(course_id: str, data: CSVDataSource = Depends(get_csv_data)):
    """Get course with chapters and lectures. Uses Qdrant in RAG mode."""
    if rag_pipeline and rag_pipeline.vector_store:
        # Qdrant stores course_title, not course_id — reverse the slug
        all_courses = rag_pipeline.vector_store.get_all_courses()
        course_title = None
        for c in all_courses:
            if c["course_id"] == course_id:
                course_title = c["course_title"]
                break
        if course_title:
            course = rag_pipeline.vector_store.get_course_detail(course_title)
            if course:
                return course
        raise HTTPException(status_code=404, detail="Course not found")

    course = data.get_course_detail(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/lectures/{lecture_id}", response_model=LectureDetail)
async def get_lecture_detail(lecture_id: str, data: CSVDataSource = Depends(get_csv_data)):
    """Get lecture metadata and transcript. Uses Qdrant in RAG mode."""
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
        # Handle LLM errors
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            return ChatResponse(
                message="Oops, looks like you've hit the rate limit! If this is a per-minute limit, just wait about **60 seconds** and try again. If you've used up your daily tokens, they reset at **midnight UTC** (every 24 hours). In the meantime, our [Discord community](" + service.discord_url + ") is always there to help!",
                isNotAnswerable=True,
                discordUrl=service.discord_url
            )
        elif "invalid api key" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        else:
            raise HTTPException(status_code=500, detail=error_msg)


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
    """SSE streaming version of RAG chat."""
    pipeline = get_rag_pipeline()

    history = [{"role": msg.role, "content": msg.content} for msg in request.history]

    # Resolve chapter/lecture titles for query enrichment (helps embedding model)
    chapter_title = ""
    lecture_title = ""
    if csv_data:
        lecture_detail = csv_data.get_lecture_detail(request.lectureId)
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

    async def event_generator():
        try:
            async for event in pipeline.process_question_stream(
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
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {error_msg}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
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
