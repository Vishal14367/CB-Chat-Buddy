'use client';

import { useState, useRef, useEffect, useCallback, memo } from 'react';
import { api } from '@/lib/api';
import { storage, ChatPreferences, ModePreference } from '@/lib/storage';
import { ChatMessage, ReferenceItem } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Image from 'next/image';

interface ChatPanelProps {
  lectureId: string;
  courseTitle?: string;
  currentLectureOrder?: number;
  playerUrl?: string;
  onMinimize?: () => void;
  onClose?: () => void;
}

interface EnrichedMessage extends ChatMessage {
  references?: ReferenceItem[];
  responseType?: string;
  showReferences?: boolean;
  _streamId?: number;
  timestamp?: Date;
}

// Professional English greetings
const GREETING_MESSAGES = [
  "Hey! I'm **Peter Pandey**, your learning buddy for this lecture. What would you like to understand better?",
  "Hi there! Peter Pandey here. Got any doubts from this lecture? Fire away!",
  "Hello! I'm **Peter Pandey**. Ready to help you understand this lecture. What's on your mind?",
  "Hey! Peter here. Ask me anything about this lecture and let's figure it out together!",
];

function formatMessageContent(content: string): string {
  return content
    .replace(/\. ([A-Z])/g, '.\n\n$1')
    .replace(/! ([A-Z])/g, '!\n\n$1')
    .replace(/\? ([A-Z])/g, '?\n\n$1');
}

function getRandomGreeting(): string {
  return GREETING_MESSAGES[Math.floor(Math.random() * GREETING_MESSAGES.length)];
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function shouldShowTimestamp(current: EnrichedMessage, previous?: EnrichedMessage): boolean {
  if (!previous || !current.timestamp || !previous.timestamp) return true;
  const diff = current.timestamp.getTime() - previous.timestamp.getTime();
  return diff > 5 * 60 * 1000;
}

// Convert [timestamp:MM:SS] markers to clickable links
function renderTimestamps(content: string, playerUrl?: string): string {
  if (!playerUrl) return content;
  return content.replace(/\[timestamp:(\d{1,2}:\d{2})\]/g, (_, time) => {
    const parts = time.split(':');
    const seconds = parseInt(parts[0]) * 60 + parseInt(parts[1]);
    return `[${time}](${playerUrl}#t=${seconds}s)`;
  });
}

// Memoized message component
const MessageBubble = memo(function MessageBubble({
  msg, idx, messages, playerUrl
}: {
  msg: EnrichedMessage;
  idx: number;
  messages: EnrichedMessage[];
  playerUrl?: string;
}) {
  return (
    <div>
      {shouldShowTimestamp(msg, messages[idx - 1]) && msg.timestamp && (
        <div className="flex justify-center mb-2">
          <span className="text-[10px] text-[#8A8690]/60 font-medium">{formatTime(msg.timestamp)}</span>
        </div>
      )}
      <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} chat-message-enter`}>
        {msg.role === 'assistant' && (
          <div className="flex-shrink-0 mr-2.5 mt-0.5">
            <Image src="/peter-avatar.png" alt="Peter" width={28} height={28} className="rounded-full" />
          </div>
        )}
        <div className={`max-w-[80%] ${
          msg.role === 'user'
            ? 'bg-[#3B82F6] text-white rounded-2xl rounded-br-md px-3.5 py-2.5'
            : 'bg-white text-[#1A1A2E] rounded-2xl rounded-bl-md px-3.5 py-2.5 border border-[#E2E5F1]'
        }`}>
          {msg.role === 'user' ? (
            <p className="text-[13px] leading-relaxed">{msg.content}</p>
          ) : (
            <div className="chat-prose">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="text-[13px] leading-relaxed text-[#1A1A2E]/90 mb-1.5 last:mb-0">{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold text-[#1A1A2E]">{children}</strong>,
                  a: ({ href, children }) => {
                    // Timestamp links get special styling
                    const isTimestamp = href?.includes('#t=') && /^\d{1,2}:\d{2}$/.test(String(children));
                    if (isTimestamp) {
                      return (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-[#3B82F6] hover:text-[#2563EB] font-medium text-[12px] bg-[#EFF6FF] px-1.5 py-0.5 rounded-md border border-[#DBEAFE] hover:border-[#3B82F6]/40 transition-colors">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          {children}
                        </a>
                      );
                    }
                    return (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#3B82F6] hover:text-[#2563EB] underline underline-offset-2 decoration-[#3B82F6]/30">{children}</a>
                    );
                  },
                  ul: ({ children }) => <ul className="list-disc ml-4 space-y-0.5 text-[13px] text-[#1A1A2E]/80">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal ml-4 space-y-0.5 text-[13px] text-[#1A1A2E]/80">{children}</ol>,
                  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                  code: ({ children }) => <code className="bg-[#EFF6FF] text-[#2563EB] px-1 py-0.5 rounded text-[12px] font-mono">{children}</code>,
                }}
              >
                {renderTimestamps(formatMessageContent(msg.content), playerUrl)}
              </ReactMarkdown>

              {/* Reference chips */}
              {(msg as EnrichedMessage).showReferences && (msg as EnrichedMessage).references && (msg as EnrichedMessage).references!.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-[#E2E5F1]">
                  <p className="text-[10px] font-medium text-[#8A8690] uppercase tracking-wider mb-1.5">Related lectures</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(msg as EnrichedMessage).references!.map((ref, refIdx) => (
                      <a key={refIdx} href={ref.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#EFF6FF] hover:bg-[#DBEAFE] text-[11px] font-medium text-[#1A1A2E]/70 rounded-md border border-[#DBEAFE] hover:border-[#3B82F6]/30 transition-colors">
                        <svg className="w-3 h-3 text-[#3B82F6]" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        <span className="truncate max-w-[140px]">{ref.lecture_title}</span>
                        <span className="text-[#8A8690]">{ref.timestamp}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

// Discord CTA card for rate-limited responses
function DiscordCTA() {
  return (
    <div className="mx-2 mb-3 p-4 bg-gradient-to-br from-[#5865F2]/10 to-[#5865F2]/5 rounded-xl border border-[#5865F2]/20 chat-message-enter">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 bg-[#5865F2] rounded-xl flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-[#1A1A2E] mb-1" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
            Need more help? Join our Discord!
          </h4>
          <p className="text-[12px] text-[#8A8690] leading-relaxed mb-2">
            You&apos;ve used up your tokens for now. Our Discord community has mentors and fellow learners who can help.
          </p>
          <div className="text-[12px] text-[#1A1A2E]/80 space-y-1.5">
            <p className="font-medium">How to join Discord:</p>
            <ol className="list-decimal ml-4 space-y-0.5 text-[#8A8690]">
              <li>Go to any lecture in your course</li>
              <li>Click the &quot;Ask questions on Discord&quot; tab</li>
              <li>Click &quot;Click here to join&quot; to join the server</li>
              <li>Having trouble? Use the &quot;Troubleshoot here&quot; link below the join button</li>
            </ol>
            <p className="text-[11px] text-[#8A8690] mt-1.5">
              Still stuck? Reach out to <span className="text-[#3B82F6]">info@codebasics.io</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({ lectureId, courseTitle, currentLectureOrder, playerUrl, onMinimize, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<EnrichedMessage[]>(() => {
    // Restore chat history from sessionStorage
    const saved = storage.getChatHistory(lectureId);
    if (saved && saved.length > 0) {
      return saved.map(m => ({
        ...m,
        timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
      })) as EnrichedMessage[];
    }
    return [];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [voiceConfidence, setVoiceConfidence] = useState(0);
  const [showRateLimitCTA, setShowRateLimitCTA] = useState(false);

  // Mode system: first-time selector, then locked for session
  const [chatMode, setChatMode] = useState<'teach' | 'direct'>('direct');
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [rememberPreference, setRememberPreference] = useState(false);
  const [modeSelected, setModeSelected] = useState(false);

  // Inline API key onboarding
  const [inlineApiKey, setInlineApiKey] = useState('');
  const [inlineVerifying, setInlineVerifying] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  // Duplicate detection
  const answeredQuestionsRef = useRef<Map<string, string>>(new Map());

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const isRecordingRef = useRef(false);

  // Load saved mode preference on mount
  useEffect(() => {
    const saved = storage.getModePreference();
    if (saved && saved.remembered) {
      // User previously chose "remember" — apply silently
      setChatMode(saved.mode);
      setModeSelected(true);
      setShowModeSelector(false);
    } else {
      // No remembered preference — show selector
      setShowModeSelector(true);
    }
  }, []);

  useEffect(() => {
    const key = storage.getGroqKey();
    setHasApiKey(!!key && storage.isKeyVerified());

    if (hasApiKey && messages.length === 0) {
      setMessages([{ role: 'assistant', content: getRandomGreeting(), timestamp: new Date() }]);
    }
  }, [hasApiKey]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Persist messages to sessionStorage on every change
  useEffect(() => {
    if (messages.length > 0) {
      const serializable = messages.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp?.toISOString(),
        references: m.references,
        responseType: m.responseType,
        showReferences: m.showReferences,
      }));
      storage.setChatHistory(lectureId, serializable);
    }
  }, [messages, lectureId]);

  // Speech Recognition (single-shot mode for stability)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 3;
    recognition.lang = 'en-IN';

    let finalTranscript = '';
    let silenceTimer: NodeJS.Timeout | null = null;

    recognition.onstart = () => {
      isRecordingRef.current = true;
      finalTranscript = '';
      setInterimText('');
      setVoiceConfidence(0);
    };

    recognition.onresult = (event: any) => {
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        const confidence = result[0].confidence;

        if (result.isFinal) {
          let bestTranscript = transcript;
          let bestConfidence = confidence;
          for (let j = 1; j < result.length; j++) {
            if (result[j].confidence > bestConfidence) {
              bestTranscript = result[j].transcript;
              bestConfidence = result[j].confidence;
            }
          }
          finalTranscript += bestTranscript + ' ';
          setVoiceConfidence(Math.round((bestConfidence || 0) * 100));
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        setInput(finalTranscript.trim());
        setInterimText(interimTranscript);
      } else {
        setInterimText(interimTranscript);
      }

      // Auto-stop after 3.5s of silence once we have a transcript
      if (silenceTimer) clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        if (finalTranscript.trim()) {
          isRecordingRef.current = false;
          try { recognition.stop(); } catch { /* ignore */ }
        }
      }, 3500);
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech') {
        // Show brief hint instead of spamming errors
        setInterimText('No speech detected. Try again.');
        setTimeout(() => {
          if (!isRecordingRef.current) setInterimText('');
        }, 2000);
        return;
      }
      if (event.error === 'aborted') return; // Expected when we call stop()
      console.error('Speech recognition error:', event.error);
      isRecordingRef.current = false;
      setIsListening(false);
      setInterimText('');
    };

    recognition.onend = () => {
      if (silenceTimer) clearTimeout(silenceTimer);

      // Only auto-restart if user is still listening AND no final transcript yet
      if (isRecordingRef.current && !finalTranscript.trim()) {
        setTimeout(() => {
          if (isRecordingRef.current) {
            try { recognition.start(); } catch { /* ignore */ }
          }
        }, 300);
        return;
      }

      // Clean stop
      isRecordingRef.current = false;
      setIsListening(false);
      setInterimText('');
      setVoiceConfidence(0);

      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(t => t.stop());
        audioStreamRef.current = null;
      }

      inputRef.current?.focus();
    };

    recognitionRef.current = recognition;

    return () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      isRecordingRef.current = false;
    };
  }, []);

  const toggleVoiceInput = useCallback(async () => {
    if (!recognitionRef.current) {
      alert('Voice input is not supported in your browser. Please use Chrome or Edge.');
      return;
    }

    if (isListening) {
      // Signal to onend not to restart
      isRecordingRef.current = false;
      try { recognitionRef.current.stop(); } catch { /* ignore */ }
      setIsListening(false);
      setInterimText('');
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(t => t.stop());
        audioStreamRef.current = null;
      }
    } else {
      if (isRecordingRef.current) return; // Prevent double-start
      setInput('');
      setInterimText('');
      setVoiceConfidence(0);

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            channelCount: 1,
          }
        });
        audioStreamRef.current = stream;
      } catch (err) {
        console.warn('Could not optimize audio pipeline:', err);
      }

      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch {
        // Graceful retry
        isRecordingRef.current = false;
        setTimeout(() => {
          try {
            recognitionRef.current.start();
            setIsListening(true);
          } catch {
            console.error('Failed to start speech recognition');
          }
        }, 300);
      }
    }
  }, [isListening]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }

    const questionText = input.trim();

    // Duplicate detection: check if exact same question was asked in this session
    if (questionText && answeredQuestionsRef.current.has(questionText.toLowerCase())) {
      const cachedAnswer = answeredQuestionsRef.current.get(questionText.toLowerCase())!;
      const userMessage: EnrichedMessage = { role: 'user', content: questionText, timestamp: new Date() };
      setMessages(prev => [...prev, userMessage, {
        role: 'assistant',
        content: cachedAnswer,
        timestamp: new Date(),
      }]);
      setInput('');
      return;
    }

    const userMessage: EnrichedMessage = { role: 'user', content: questionText, timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setIsTyping(true);
    setShowRateLimitCTA(false);

    if (inputRef.current) inputRef.current.style.height = 'auto';

    try {
      const apiKey = storage.getGroqKey();
      if (!apiKey) throw new Error('API key not found');

      if (courseTitle && currentLectureOrder !== undefined) {
        let streamedContent = '';
        const streamingMsgId = Date.now();

        await api.chatStream(
          {
            apiKey,
            message: questionText,
            courseTitle,
            currentLectureOrder,
            lectureId,
            history: messages.map(m => ({ role: m.role, content: m.content })),
            teachingMode: chatMode === 'teach' ? 'teach' : 'fix',
            responseStyle: chatMode === 'teach' ? 'casual' : 'direct',
          },
          (token) => {
            streamedContent += token;
            setIsTyping(false);
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m._streamId === streamingMsgId);
              if (msgIndex !== -1) {
                updated[msgIndex] = { ...updated[msgIndex], content: streamedContent };
                return updated;
              }
              return [...prev, { role: 'assistant', content: streamedContent, _streamId: streamingMsgId, timestamp: new Date() }];
            });
          },
          (references, responseType, showReferences) => {
            // Check for rate limiting
            if (responseType === 'rate_limited') {
              setShowRateLimitCTA(true);
            }

            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m._streamId === streamingMsgId);
              if (msgIndex !== -1) {
                updated[msgIndex] = { ...updated[msgIndex], references, responseType, showReferences, _streamId: undefined } as EnrichedMessage;

                // Cache the answer for duplicate detection
                if (questionText) {
                  answeredQuestionsRef.current.set(questionText.toLowerCase(), updated[msgIndex].content);
                }

                return updated;
              }
              return updated;
            });
          },
          (error) => {
            setIsTyping(false);
            let errorDisplay = error;
            if (error.toLowerCase().includes('rate') || error.includes('429') || error.toLowerCase().includes('token')) {
              setShowRateLimitCTA(true);
              errorDisplay = "You've hit the rate limit. Wait about **60 seconds** for per-minute limits, or tokens reset at **midnight UTC** for daily limits.";
            }
            setMessages((prev) => [...prev, { role: 'assistant', content: errorDisplay, timestamp: new Date() }]);
          }
        );
      } else {
        const response = await api.chat({ apiKey, lectureId, message: userMessage.content, history: messages });
        setIsTyping(false);
        setMessages((prev) => [...prev, { role: 'assistant', content: response.message, timestamp: new Date() }]);
      }
    } catch (err: any) {
      setIsTyping(false);
      const errorMsg = err.message || '';
      let displayMsg = 'Something went wrong. Please try again.';
      if (errorMsg.toLowerCase().includes('rate limit') || errorMsg.includes('429') || errorMsg.toLowerCase().includes('token')) {
        setShowRateLimitCTA(true);
        displayMsg = "You've hit the rate limit. Wait about **60 seconds** for per-minute limits, or tokens reset at **midnight UTC** for daily limits.";
      } else if (errorMsg.toLowerCase().includes('api key') || errorMsg.includes('401')) {
        displayMsg = "There's an issue with your API key. Head over to **Settings** to update it.";
      } else if (errorMsg) {
        displayMsg = errorMsg;
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: displayMsg, timestamp: new Date() }]);
    } finally {
      setLoading(false);
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  // Handle first-time mode selection
  const handleModeSelect = (mode: 'teach' | 'direct') => {
    setChatMode(mode);
    setModeSelected(true);
    setShowModeSelector(false);

    // Also update ChatPreferences for backend compat
    storage.setChatPreferences({
      teachingMode: mode === 'teach' ? 'teach' : 'fix',
      responseStyle: mode === 'teach' ? 'casual' : 'direct',
    });

    if (rememberPreference) {
      storage.setModePreference({ mode, remembered: true });
    } else {
      // Session only — clear any old preference
      storage.clearModePreference();
    }
  };

  // Inline API key verification handler
  const handleInlineVerify = async () => {
    if (!inlineApiKey.trim()) return;
    setInlineVerifying(true);
    setInlineError(null);
    try {
      const response = await api.verifyApiKey({ apiKey: inlineApiKey.trim() });
      if (response.ok) {
        storage.setGroqKey(inlineApiKey.trim());
        storage.setKeyVerified(true);
        setHasApiKey(true);
        setInlineApiKey('');
      } else {
        setInlineError(response.message || 'Invalid API key. Please check and try again.');
      }
    } catch (err: any) {
      setInlineError(err.message || 'Verification failed. Please try again.');
    } finally {
      setInlineVerifying(false);
    }
  };

  // No API key — inline onboarding
  if (!hasApiKey) {
    return (
      <div className="h-full flex flex-col bg-white overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 bg-white border-b border-[#E2E5F1] flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Image src="/peter-avatar.png" alt="Peter Pandey" width={36} height={36} className="rounded-full" />
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-[#F89937] rounded-full border-[1.5px] border-white"></div>
            </div>
            <div>
              <h3 className="text-[#1A1A2E] text-sm font-semibold leading-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                Peter Pandey
              </h3>
              <p className="text-[11px] text-[#F89937] leading-tight mt-0.5">Setting up...</p>
            </div>
          </div>
        </div>

        {/* Onboarding form */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          <div className="w-full max-w-xs text-center">
            <div className="mb-4">
              <p className="text-[14px] font-semibold text-[#1A1A2E] mb-1" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                Hey! I&apos;m Peter Pandey
              </p>
              <p className="text-[12px] text-[#8A8690] leading-relaxed">
                Before we start, I need your Groq API key. It&apos;s free and takes 30 seconds.
              </p>
            </div>

            <div className="space-y-3">
              <input
                type="password"
                value={inlineApiKey}
                onChange={(e) => { setInlineApiKey(e.target.value); setInlineError(null); }}
                placeholder="gsk_..."
                className="w-full px-3.5 py-2.5 bg-[#FAFAFA] border border-[#E2E5F1] rounded-lg focus:outline-none focus:border-[#3B82F6]/40 focus:bg-white transition-all text-sm placeholder-[#8A8690]"
                onKeyDown={(e) => e.key === 'Enter' && handleInlineVerify()}
              />
              <button
                onClick={handleInlineVerify}
                disabled={inlineVerifying || !inlineApiKey.trim()}
                className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white px-4 py-2.5 rounded-lg disabled:bg-[#E2E5F1] disabled:text-[#8A8690] disabled:cursor-not-allowed transition-colors text-sm font-medium"
              >
                {inlineVerifying ? 'Verifying...' : 'Save & Start Chatting'}
              </button>
              {inlineError && (
                <p className="text-[12px] text-[#DC2626]">{inlineError}</p>
              )}
              <a
                href="https://console.groq.com/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-[#3B82F6] hover:underline font-medium"
              >
                Get free API key
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 flex flex-col bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-[#E2E5F1] flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Image src="/peter-avatar.png" alt="Peter Pandey" width={36} height={36} className="rounded-full" />
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-[#10B981] rounded-full border-[1.5px] border-white"></div>
            </div>
            <div>
              <h3 className="text-[#1A1A2E] text-sm font-semibold leading-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                Peter Pandey
              </h3>
              <p className="text-[11px] leading-tight mt-0.5">
                {isTyping ? (
                  <span className="text-[#3B82F6]">typing...</span>
                ) : (
                  <span className="text-[#10B981]">Online</span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {onMinimize && (
              <button
                onClick={onMinimize}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[#8A8690] hover:text-[#1A1A2E] hover:bg-[#F3F4F6] transition-all"
                title="Minimize chat"
                aria-label="Minimize chat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.5 12h-15" />
                </svg>
              </button>
            )}
            {onClose && (
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[#8A8690] hover:text-[#EF4444] hover:bg-[#FEF2F2] transition-all"
                title="Close chat"
                aria-label="Close chat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 relative overflow-y-auto px-4 py-4 space-y-3 bg-[#FAFAFA]" role="log" aria-live="polite">
        {/* First-time mode selector overlay */}
        {showModeSelector && (
          <div className="absolute inset-0 z-10 bg-white/95 backdrop-blur-sm flex items-center justify-center px-6">
            <div className="w-full max-w-xs text-center">
              <div className="mb-5">
                <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#EFF6FF] flex items-center justify-center">
                  <svg className="w-6 h-6 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                </div>
                <p className="text-[15px] font-semibold text-[#1A1A2E] mb-1" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                  How would you like me to help?
                </p>
                <p className="text-[12px] text-[#8A8690] leading-relaxed">
                  Choose your preferred chat style
                </p>
              </div>
              <div className="space-y-2.5 mb-4">
                <button
                  onClick={() => handleModeSelect('teach')}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-[#3B82F6]/20 bg-[#EFF6FF] text-left transition-all hover:border-[#3B82F6] hover:shadow-md group"
                >
                  <p className="text-[13px] font-semibold text-[#3B82F6] group-hover:text-[#2563EB]">Smart Friend</p>
                  <p className="text-[11px] text-[#8A8690] mt-0.5">Guides you to discover the answer yourself</p>
                </button>
                <button
                  onClick={() => handleModeSelect('direct')}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-[#E2E5F1] bg-white text-left transition-all hover:border-[#3B82F6]/40 hover:shadow-md group"
                >
                  <p className="text-[13px] font-semibold text-[#1A1A2E] group-hover:text-[#3B82F6]">Direct</p>
                  <p className="text-[11px] text-[#8A8690] mt-0.5">Gives you a straight, concise answer</p>
                </button>
              </div>
              <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberPreference}
                  onChange={(e) => setRememberPreference(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-[#E2E5F1] text-[#3B82F6] focus:ring-[#3B82F6]/30"
                />
                <span className="text-[11px] text-[#8A8690]">Remember my preference</span>
              </label>
            </div>
          </div>
        )}
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} msg={msg} idx={idx} messages={messages} playerUrl={playerUrl} />
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex justify-start items-start chat-message-enter">
            <div className="flex-shrink-0 mr-2.5 mt-0.5">
              <Image src="/peter-avatar.png" alt="Peter" width={28} height={28} className="rounded-full opacity-60" />
            </div>
            <div className="bg-white rounded-2xl rounded-bl-md px-4 py-3 border border-[#E2E5F1]">
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-[#3B82F6] rounded-full typing-dot"></div>
                <div className="w-1.5 h-1.5 bg-[#3B82F6] rounded-full typing-dot"></div>
                <div className="w-1.5 h-1.5 bg-[#3B82F6] rounded-full typing-dot"></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Discord CTA for rate-limited responses */}
      {showRateLimitCTA && <DiscordCTA />}

      {/* Voice recording bar */}
      {isListening && (
        <div className="px-4 py-2.5 bg-[#EFF6FF] border-t border-[#DBEAFE] flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 bg-[#3B82F6] rounded-full animate-pulse"></div>
            <div className="flex items-center gap-0.5 h-5">
              <div className="voice-bar"></div>
              <div className="voice-bar"></div>
              <div className="voice-bar"></div>
              <div className="voice-bar"></div>
              <div className="voice-bar"></div>
            </div>
            <span className="text-xs font-medium text-[#3B82F6] max-w-[200px] truncate">
              {interimText || input || 'Listening... speak now'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {voiceConfidence > 0 && (
              <span className="text-[10px] text-[#8A8690]">{voiceConfidence}%</span>
            )}
            <button onClick={toggleVoiceInput} className="text-xs font-medium text-[#2563EB] hover:text-[#3B82F6] transition-colors">
              Done
            </button>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="px-3 py-3 border-t border-[#E2E5F1] bg-white flex-shrink-0">
        <div className="flex items-end gap-2">
          {/* Voice button */}
          <button
            onClick={toggleVoiceInput}
            disabled={loading}
            className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
              isListening
                ? 'bg-[#3B82F6] text-white voice-pulse'
                : 'bg-[#EFF6FF] text-[#8A8690] hover:text-[#3B82F6] hover:bg-[#DBEAFE]'
            } disabled:opacity-40`}
            title="Voice input (English & Hinglish)"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </button>

          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask about this lecture..."
              maxLength={1000}
              disabled={loading}
              rows={1}
              className="w-full px-3.5 py-2 bg-[#FAFAFA] border border-[#E2E5F1] rounded-xl focus:outline-none focus:border-[#3B82F6]/40 focus:bg-white disabled:opacity-50 text-[13px] transition-all placeholder-[#8A8690] resize-none leading-relaxed"
              style={{ minHeight: '36px', maxHeight: '120px' }}
            />
          </div>

          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
              !input.trim() || loading
                ? 'bg-[#E2E5F1] text-[#8A8690]'
                : 'bg-[#3B82F6] hover:bg-[#2563EB] text-white'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>

        {/* Powered by Groq badge */}
        <div className="flex justify-center mt-2">
          <span className="text-[9px] text-[#8A8690]/50 font-medium tracking-wide">Peter Pandey is still learning and may make mistakes.</span>
        </div>
      </div>
    </div>
  );
}
