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

/** Default timeout for non-streaming requests (ms). */
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Create a fetch call with an AbortController timeout.
 * Automatically aborts and throws a descriptive error if the request
 * takes longer than `timeoutMs` milliseconds.
 */
function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(input, { ...init, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

export const api = {
  async getCourses(): Promise<Course[]> {
    const res = await fetchWithTimeout(`${API_BASE_URL}/courses`);
    if (!res.ok) throw new Error('Failed to fetch courses');
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error('Unexpected response format for courses');
    return data;
  },

  async getCourseDetail(courseId: string): Promise<CourseDetail> {
    const res = await fetchWithTimeout(`${API_BASE_URL}/courses/${encodeURIComponent(courseId)}`);
    if (!res.ok) throw new Error('Failed to fetch course detail');
    const data = await res.json();
    if (!data || typeof data !== 'object') throw new Error('Unexpected response format for course detail');
    return data;
  },

  async getLectureDetail(lectureId: string): Promise<LectureDetail> {
    const res = await fetchWithTimeout(`${API_BASE_URL}/lectures/${encodeURIComponent(lectureId)}`);
    if (!res.ok) throw new Error('Failed to fetch lecture detail');
    const data = await res.json();
    if (!data || typeof data !== 'object') throw new Error('Unexpected response format for lecture detail');
    return data;
  },

  async verifyApiKey(request: VerifyKeyRequest): Promise<VerifyKeyResponse> {
    const res = await fetchWithTimeout(
      `${API_BASE_URL}/llm/verify`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      },
      15_000 // shorter timeout for key verification
    );
    if (!res.ok) throw new Error('Failed to verify API key');
    return res.json();
  },

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const res = await fetchWithTimeout(
      `${API_BASE_URL}/chat`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      }
    );
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
    // Streaming uses a separate AbortController so the caller can cancel if needed;
    // no hard timeout here — LLM streaming can legitimately take 30+ seconds.
    const controller = new AbortController();

    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/v2/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error';
      onError(msg === 'The user aborted a request.' ? 'Request cancelled' : msg);
      return;
    }

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

    try {
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
    } finally {
      reader.releaseLock();
    }
  },
};
