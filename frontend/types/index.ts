export interface Lecture {
  lecture_id: string;
  lecture_title: string;
  thumbnail_url?: string;
  duration?: number;
  lecture_order?: number;
}

export interface LectureDetail extends Lecture {
  transcript: string;
  course_title: string;
  chapter_title: string;
}

export interface Chapter {
  chapter_title: string;
  lectures: Lecture[];
}

export interface Course {
  course_id: string;
  course_title: string;
  chapter_count?: number;
  lecture_count?: number;
}

export interface CourseDetail extends Course {
  chapters: Chapter[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  apiKey: string;
  lectureId: string;
  message: string;
  history: ChatMessage[];
}

export interface ChatResponse {
  message: string;
  isNotAnswerable: boolean;
  discordUrl?: string;
}

export interface VerifyKeyRequest {
  apiKey: string;
}

export interface VerifyKeyResponse {
  ok: boolean;
  message?: string;
}

// --- RAG v2 Types ---

export interface ReferenceItem {
  lecture_title: string;
  chapter_title: string;
  timestamp: string;
  url: string;
}

export interface RAGChatRequest {
  apiKey: string;
  message: string;
  courseTitle: string;
  currentLectureOrder: number;
  lectureId: string;
  history: ChatMessage[];
  teachingMode?: 'teach' | 'fix';
  responseStyle?: 'casual' | 'direct';
  hintStage?: number;
  imageBase64?: string;
}

export interface RAGChatResponse {
  message: string;
  references: ReferenceItem[];
  responseType: string;
  cacheHit: boolean;
  isNotAnswerable: boolean;
  discordUrl?: string;
}

export interface SSETokenEvent {
  type: 'token';
  content: string;
}

export interface SSEDoneEvent {
  type: 'done';
  references: ReferenceItem[];
  responseType: string;
  cacheHit?: boolean;
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent;
