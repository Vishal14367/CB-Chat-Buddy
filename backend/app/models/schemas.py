from pydantic import BaseModel, field_validator
from typing import List, Optional

class Lecture(BaseModel):
    lecture_id: str
    lecture_title: str
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
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

class CourseDetail(Course):
    chapters: List[Chapter]

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

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
    history: List[ChatMessage] = []
    teachingMode: Optional[str] = "fix"       # "teach" (Socratic) or "fix" (direct answer)
    responseStyle: Optional[str] = "casual"    # "casual" (beginner-friendly) or "direct" (concise)
    hintStage: Optional[int] = 1              # 1-3: progressive hint ladder stage
    imageBase64: Optional[str] = None          # base64-encoded screenshot for vision analysis

    @field_validator('lectureId')
    @classmethod
    def lecture_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('lectureId must be a non-empty string')
        return v.strip()

    @field_validator('courseTitle')
    @classmethod
    def course_title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('courseTitle must be a non-empty string')
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

class RAGChatResponse(BaseModel):
    message: str
    references: List[ReferenceItem] = []
    responseType: str = "in_scope"
    cacheHit: bool = False
    isNotAnswerable: bool = False
    discordUrl: Optional[str] = None
