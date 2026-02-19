import {
  Course,
  CourseDetail,
  LectureDetail,
  ChatRequest,
  ChatResponse,
  VerifyKeyRequest,
  VerifyKeyResponse,
  RAGChatRequest,
  ReferenceItem,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const api = {
  async getCourses(): Promise<Course[]> {
    const res = await fetch(`${API_BASE_URL}/courses`);
    if (!res.ok) throw new Error('Failed to fetch courses');
    return res.json();
  },

  async getCourseDetail(courseId: string): Promise<CourseDetail> {
    const res = await fetch(`${API_BASE_URL}/courses/${courseId}`);
    if (!res.ok) throw new Error('Failed to fetch course detail');
    return res.json();
  },

  async getLectureDetail(lectureId: string): Promise<LectureDetail> {
    const res = await fetch(`${API_BASE_URL}/lectures/${lectureId}`);
    if (!res.ok) throw new Error('Failed to fetch lecture detail');
    return res.json();
  },

  async verifyApiKey(request: VerifyKeyRequest): Promise<VerifyKeyResponse> {
    const res = await fetch(`${API_BASE_URL}/llm/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error('Failed to verify API key');
    return res.json();
  },

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to chat' }));
      throw new Error(error.detail || 'Failed to chat');
    }
    return res.json();
  },

  async chatStream(
    request: RAGChatRequest,
    onToken: (token: string) => void,
    onDone: (references: ReferenceItem[], responseType: string, showReferences?: boolean) => void,
    onError: (error: string) => void
  ): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/v2/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to chat' }));
      onError(error.detail || 'Failed to chat');
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError('Streaming not supported');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'token') {
              onToken(data.content);
            } else if (data.type === 'error') {
              onError(data.content || 'An error occurred');
            } else if (data.type === 'done') {
              onDone(data.references || [], data.responseType || 'in_scope', data.showReferences ?? true);
            }
          } catch {
            // Skip malformed events
          }
        }
      }
    }
  },
};
