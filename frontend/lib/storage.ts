const GROQ_KEY_STORAGE_KEY = 'groq_api_key';
const GROQ_KEY_VERIFIED_KEY = 'groq_key_verified';
const CHAT_PREFS_KEY = 'chat_preferences';
const CHAT_TOOLTIP_DISMISSED_KEY = 'chat_tooltip_dismissed';

export interface ChatPreferences {
  teachingMode: 'teach' | 'fix';
  responseStyle: 'casual' | 'direct';
}

export const storage = {
  setGroqKey(key: string) {
    if (typeof window !== 'undefined') {
      localStorage.setItem(GROQ_KEY_STORAGE_KEY, key);
    }
  },

  getGroqKey(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(GROQ_KEY_STORAGE_KEY);
    }
    return null;
  },

  removeGroqKey() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(GROQ_KEY_STORAGE_KEY);
      localStorage.removeItem(GROQ_KEY_VERIFIED_KEY);
    }
  },

  setKeyVerified(verified: boolean) {
    if (typeof window !== 'undefined') {
      localStorage.setItem(GROQ_KEY_VERIFIED_KEY, verified.toString());
    }
  },

  isKeyVerified(): boolean {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(GROQ_KEY_VERIFIED_KEY) === 'true';
    }
    return false;
  },

  getMaskedKey(): string | null {
    const key = this.getGroqKey();
    if (!key) return null;
    if (key.length <= 8) return '***';
    return key.slice(0, 4) + '***' + key.slice(-4);
  },

  // --- Chat Preferences ---

  setChatPreferences(prefs: ChatPreferences) {
    if (typeof window !== 'undefined') {
      localStorage.setItem(CHAT_PREFS_KEY, JSON.stringify(prefs));
    }
  },

  getChatPreferences(): ChatPreferences | null {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(CHAT_PREFS_KEY);
      if (saved) {
        try {
          return JSON.parse(saved) as ChatPreferences;
        } catch {
          return null;
        }
      }
    }
    return null;
  },

  clearChatPreferences() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(CHAT_PREFS_KEY);
    }
  },

  // --- Chat Tooltip ---

  hasSeenChatTooltip(): boolean {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(CHAT_TOOLTIP_DISMISSED_KEY) === 'true';
    }
    return false;
  },

  dismissChatTooltip() {
    if (typeof window !== 'undefined') {
      localStorage.setItem(CHAT_TOOLTIP_DISMISSED_KEY, 'true');
    }
  },

  // --- Chat History (sessionStorage — per-tab, clears on tab close) ---

  setChatHistory(lectureId: string, messages: Array<{ role: string; content: string; timestamp?: string; references?: any; responseType?: string; showReferences?: boolean }>) {
    if (typeof window !== 'undefined') {
      try {
        const capped = messages.slice(-50);
        sessionStorage.setItem('chat_history_' + lectureId, JSON.stringify(capped));
      } catch {
        // sessionStorage quota exceeded — silently fail
      }
    }
  },

  getChatHistory(lectureId: string): Array<{ role: string; content: string; timestamp?: string; references?: any; responseType?: string; showReferences?: boolean }> | null {
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('chat_history_' + lectureId);
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {
          return null;
        }
      }
    }
    return null;
  },

  clearChatHistory(lectureId: string) {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('chat_history_' + lectureId);
    }
  },
};
