from pydantic import BaseModel, field_validator
from typing import List, Optional

class Lecture(BaseModel):
    lecture_id: str
    lecture_title: str
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    lecture_order: Optional[int] = None

class LectureDetail(Lecture):
    transcript: str
    course_title: str
    chapter_title: str

class Chapter(BaseModel):
    chapter_title: str
    lectures: List[Lecture]

class Course(BaseModel):
    course_id: str
    course_title: str
    chapter_count: Optional[int] = None
    lecture_count: Optional[int] = None
    category: Optional[str] = None

class CourseDetail(Course):
    chapters: List[Chapter]

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    responseType: Optional[str] = None  # "in_scope", "off_topic", "covered_elsewhere", etc.

class ChatRequest(BaseModel):
    apiKey: str
    lectureId: str
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    message: str
    isNotAnswerable: bool = False
    discordUrl: Optional[str] = None

class VerifyKeyRequest(BaseModel):
    apiKey: str

class VerifyKeyResponse(BaseModel):
    ok: bool
    message: Optional[str] = None


# --- RAG Pipeline Models (v2) ---

class ReferenceItem(BaseModel):
    lecture_title: str
    chapter_title: str
    timestamp: str
    url: str

class RAGChatRequest(BaseModel):
    apiKey: str
    message: str
    courseTitle: str
    currentLectureOrder: int
    lectureId: str
    history: List[ChatMessage] = []           # max 50 messages enforced by validator
    teachingMode: Optional[str] = "fix"       # "teach" (Socratic) or "fix" (direct answer)
    responseStyle: Optional[str] = "casual"    # "casual" (beginner-friendly) or "direct" (concise)
    hintStage: Optional[int] = 1              # 1-3: progressive hint ladder stage
    imageBase64: Optional[str] = None          # base64-encoded screenshot for vision analysis

    @field_validator('lectureId')
    @classmethod
    def lecture_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('lectureId must be a non-empty string')
        if len(v) > 200:
            raise ValueError('lectureId must be 200 characters or less')
        return v.strip()

    @field_validator('courseTitle')
    @classmethod
    def course_title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('courseTitle must be a non-empty string')
        if len(v) > 500:
            raise ValueError('courseTitle must be 500 characters or less')
        return v.strip()

    @field_validator('currentLectureOrder')
    @classmethod
    def lecture_order_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError('currentLectureOrder must be >= 0')
        return v

    @field_validator('message')
    @classmethod
    def message_valid_length(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('message must not be empty')
        if len(v) > 1000:
            raise ValueError('message must be 1000 characters or less')
        return v

    @field_validator('history')
    @classmethod
    def history_max_length(cls, v: List['ChatMessage']) -> List['ChatMessage']:
        if len(v) > 50:
            raise ValueError('history must contain 50 messages or fewer')
        return v

    @field_validator('imageBase64')
    @classmethod
    def image_max_size(cls, v: Optional[str]) -> Optional[str]:
        # ~5 MB decoded ≈ 6.9 M base64 chars (4/3 ratio)
        if v is not None and len(v) > 7_000_000:
            raise ValueError('imageBase64 must be 5 MB or smaller')
        return v

class RAGChatResponse(BaseModel):
    message: str
    references: List[ReferenceItem] = []
    responseType: str = "in_scope"
    cacheHit: bool = False
    isNotAnswerable: bool = False
    discordUrl: Optional[str] = None
