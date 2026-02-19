'use client';

import { useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';
import { storage } from '@/lib/storage';
import { LectureDetail } from '@/types';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import ChatPanel from '@/components/ChatPanel';

type ChatState = 'open' | 'minimized' | 'closed';

export default function LecturePage() {
  const params = useParams();
  const courseId = params.courseId as string;
  const lectureId = params.lectureId as string;

  const [lecture, setLecture] = useState<LectureDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'video' | 'transcript'>('video');
  const [chatState, setChatState] = useState<ChatState>('open');
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipTimerRef = useRef<NodeJS.Timeout | null>(null);
  const inactivityTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    async function loadLecture() {
      try {
        const data = await api.getLectureDetail(lectureId);
        setLecture(data);
      } catch (err) {
        setError('Failed to load lecture');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadLecture();
  }, [lectureId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && chatState === 'open') setChatState('minimized');
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [chatState]);

  // Discoverability: first-time tooltip + inactivity trigger
  useEffect(() => {
    if (chatState === 'open') {
      // Chat is open, dismiss tooltip and clear timers
      setShowTooltip(false);
      if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current);
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      // Mark as seen when user opens chat
      storage.dismissChatTooltip();
      return;
    }

    // Only show tooltip if not dismissed before
    if (storage.hasSeenChatTooltip()) return;

    // Show tooltip after short delay for first-time users
    tooltipTimerRef.current = setTimeout(() => {
      setShowTooltip(true);
      // Auto-dismiss after 8 seconds
      setTimeout(() => setShowTooltip(false), 8000);
    }, 2000);

    // Inactivity trigger: show tooltip again after 45s if chat not opened
    inactivityTimerRef.current = setTimeout(() => {
      if (!storage.hasSeenChatTooltip()) {
        setShowTooltip(true);
        setTimeout(() => setShowTooltip(false), 8000);
      }
    }, 45000);

    return () => {
      if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current);
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    };
  }, [chatState]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-7 h-7 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-[#8A8690]">Loading lecture...</p>
        </div>
      </div>
    );
  }

  if (error || !lecture) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <p className="text-[#1A1A2E] font-medium">{error || 'Lecture not found'}</p>
      </div>
    );
  }

  const isChatVisible = chatState !== 'closed';
  const isChatOpen = chatState === 'open';
  const isChatMinimized = chatState === 'minimized';

  // Player URL for timestamp teleporter
  const playerUrl = lecture.thumbnail_url || undefined;

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      {/* Desktop layout: side-by-side */}
      <div className="flex h-[calc(100vh-57px)]">
        {/* Left: Lecture content */}
        <div className={`flex-1 min-w-0 overflow-y-auto transition-all duration-300 ${isChatOpen ? 'lg:mr-0' : ''}`}>
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            {/* Breadcrumb */}
            <div className="mb-5 flex items-center gap-1.5 text-xs text-[#8A8690]">
              <Link href="/courses" className="hover:text-[#3B82F6] transition-colors">Courses</Link>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
              <Link href={`/courses/${courseId}`} className="hover:text-[#3B82F6] transition-colors max-w-[180px] truncate">{lecture.course_title}</Link>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
              <span className="text-[#1A1A2E] truncate max-w-[200px]">{lecture.lecture_title}</span>
            </div>

            {/* Lecture header */}
            <div className="bg-white rounded-xl border border-[#E2E5F1] p-5 mb-5">
              <p className="text-[11px] font-medium text-[#3B82F6] uppercase tracking-wider mb-1.5">{lecture.chapter_title}</p>
              <h1 className="text-lg font-bold text-[#1A1A2E] tracking-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>{lecture.lecture_title}</h1>
            </div>

            {/* Video / Transcript tabs */}
            <div className="bg-white rounded-xl border border-[#E2E5F1] overflow-hidden">
              <div className="border-b border-[#E2E5F1] flex">
                <button onClick={() => setActiveTab('video')} className={`px-5 py-3 text-[13px] font-medium transition-all relative ${activeTab === 'video' ? 'text-[#3B82F6]' : 'text-[#8A8690] hover:text-[#1A1A2E]'}`}>
                  Video
                  {activeTab === 'video' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[#3B82F6]"></div>}
                </button>
                <button onClick={() => setActiveTab('transcript')} className={`px-5 py-3 text-[13px] font-medium transition-all relative ${activeTab === 'transcript' ? 'text-[#3B82F6]' : 'text-[#8A8690] hover:text-[#1A1A2E]'}`}>
                  Transcript
                  {activeTab === 'transcript' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[#3B82F6]"></div>}
                </button>
              </div>
              <div className="p-5">
                {activeTab === 'video' && (
                  <div className="aspect-video bg-[#0C1228] rounded-lg overflow-hidden relative">
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="text-center">
                        <div className="w-16 h-16 mx-auto mb-4 bg-white/10 hover:bg-[#3B82F6] rounded-full flex items-center justify-center cursor-pointer transition-all group">
                          <svg className="w-7 h-7 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        </div>
                        <p className="text-white/90 font-semibold text-sm mb-1" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>{lecture.lecture_title}</p>
                        <p className="text-white/40 text-xs">Watch on codebasics.io</p>
                        <a href={lecture.thumbnail_url || 'https://codebasics.io'} target="_blank" rel="noopener noreferrer" className="inline-block mt-4 bg-[#3B82F6] hover:bg-[#2563EB] text-white px-5 py-2 rounded-lg text-xs font-semibold transition-colors">
                          Watch Video
                        </a>
                      </div>
                    </div>
                  </div>
                )}
                {activeTab === 'transcript' && (
                  <div className="bg-[#FAFAFA] rounded-lg border border-[#E2E5F1]/50">
                    {lecture.transcript ? (
                      <div className="whitespace-pre-wrap text-[#1A1A2E]/80 text-sm leading-relaxed max-h-[500px] overflow-y-auto p-5 scrollbar-hide">{lecture.transcript}</div>
                    ) : (
                      <div className="py-16 text-center"><p className="text-[#8A8690] text-sm">No transcript available for this lecture.</p></div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Chat side-panel (Desktop) */}
        <div className={`hidden lg:flex flex-col min-h-0 border-l border-[#E2E5F1] bg-white transition-all duration-300 ease-in-out flex-shrink-0 ${
          isChatOpen ? 'w-[400px]' : isChatMinimized ? 'w-[52px]' : 'w-0'
        }`}>
          {/* Minimized strip */}
          {isChatMinimized && (
            <div className="h-full flex flex-col items-center py-4 gap-3">
              <button
                onClick={() => setChatState('open')}
                className="w-9 h-9 bg-[#3B82F6] hover:bg-[#2563EB] rounded-xl flex items-center justify-center transition-all hover:scale-105 active:scale-95 group relative"
                aria-label="Open chat"
                title="Open Peter Pandey"
              >
                <svg className="w-4.5 h-4.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                </svg>
                <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-[#10B981] rounded-full border-[1.5px] border-white"></div>
              </button>
              <span className="text-[10px] text-[#8A8690] font-medium writing-mode-vertical" style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}>
                Peter Pandey
              </span>
            </div>
          )}

          {/* Full chat panel */}
          {isChatOpen && (
            <div className="flex flex-col h-full min-h-0 animate-fade-in">
              <ChatPanel
                lectureId={lectureId}
                courseTitle={lecture.course_title}
                currentLectureOrder={lecture.lecture_order ?? 0}
                playerUrl={playerUrl}
                onMinimize={() => setChatState('minimized')}
                onClose={() => setChatState('closed')}
              />
            </div>
          )}
        </div>
      </div>

      {/* Mobile: Floating Chat Button */}
      <div className="lg:hidden">
        {chatState !== 'open' && (
          <div className="fixed bottom-6 right-6 z-50">
            {/* Tooltip */}
            {showTooltip && (
              <div className="absolute bottom-full right-0 mb-3 animate-scale-in">
                <div className="bg-[#1A1A2E] text-white px-4 py-2.5 rounded-xl shadow-lg max-w-[220px]">
                  <p className="text-[12px] font-medium leading-snug">Have a doubt? Ask Peter Pandey!</p>
                  <div className="absolute top-full right-5 w-2.5 h-2.5 bg-[#1A1A2E] rotate-45 -mt-1.5"></div>
                </div>
              </div>
            )}
            <button onClick={() => setChatState('open')} className="group flex items-center" aria-label="Ask Peter Pandey">
              <div className="relative flex items-center">
                <div className={`flex items-center gap-2 bg-[#3B82F6] hover:bg-[#2563EB] rounded-2xl shadow-lg shadow-[#3B82F6]/25 px-4 py-3 transition-all hover:scale-105 active:scale-95 ${chatState === 'closed' && !storage.hasSeenChatTooltip() ? 'animate-pulse-chat' : ''}`}>
                  <svg className="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                  </svg>
                  <span className="text-white text-[13px] font-semibold whitespace-nowrap">Got a doubt? Ask Peter!</span>
                </div>
                <div className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-[#10B981] rounded-full border-2 border-[#FAFAFA]"></div>
              </div>
            </button>
          </div>
        )}

        {/* Mobile: Chat bottom sheet */}
        {chatState === 'open' && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-end animate-fade-in" onClick={() => setChatState('closed')}>
            <div className="relative w-full h-[85dvh] flex flex-col animate-slide-up" onClick={(e) => e.stopPropagation()}>
              <div className="flex-1 overflow-hidden rounded-t-2xl shadow-2xl">
                <ChatPanel
                  lectureId={lectureId}
                  courseTitle={lecture.course_title}
                  currentLectureOrder={lecture.lecture_order ?? 0}
                  playerUrl={playerUrl}
                  onMinimize={() => setChatState('closed')}
                  onClose={() => setChatState('closed')}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Desktop: Reopen button when chat is fully closed */}
      {chatState === 'closed' && (
        <div className="hidden lg:block fixed bottom-6 right-6 z-50">
          {/* Tooltip */}
          {showTooltip && (
            <div className="absolute bottom-full right-0 mb-3 animate-scale-in">
              <div className="bg-[#1A1A2E] text-white px-4 py-2.5 rounded-xl shadow-lg max-w-[220px]">
                <p className="text-[12px] font-medium leading-snug">Have a doubt? Ask Peter Pandey!</p>
                <div className="absolute top-full right-5 w-2.5 h-2.5 bg-[#1A1A2E] rotate-45 -mt-1.5"></div>
              </div>
            </div>
          )}
          <button
            onClick={() => setChatState('open')}
            className="group flex items-center"
            aria-label="Ask Peter Pandey"
          >
            <div className="relative flex items-center">
              <div className={`flex items-center gap-2 bg-[#3B82F6] hover:bg-[#2563EB] rounded-2xl shadow-lg shadow-[#3B82F6]/25 px-4 py-3 transition-all hover:scale-105 active:scale-95 ${!storage.hasSeenChatTooltip() ? 'animate-pulse-chat' : ''}`}>
                <svg className="w-5 h-5 text-white flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                </svg>
                <span className="text-white text-[13px] font-semibold whitespace-nowrap">Got a doubt? Ask Peter!</span>
              </div>
              <div className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-[#10B981] rounded-full border-2 border-[#FAFAFA]"></div>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
