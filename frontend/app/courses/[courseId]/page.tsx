'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { CourseDetail } from '@/types';
import Link from 'next/link';
import { useParams } from 'next/navigation';

export default function CourseDetailPage() {
  const params = useParams();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function loadCourse() {
      try {
        const data = await api.getCourseDetail(courseId);
        setCourse(data);
        if (data.chapters.length > 0) {
          setExpandedChapters(new Set([data.chapters[0].chapter_title]));
        }
      } catch (err) {
        setError('Failed to load course');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadCourse();
  }, [courseId]);

  const toggleChapter = (chapterTitle: string) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterTitle)) next.delete(chapterTitle);
      else next.add(chapterTitle);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-7 h-7 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-[#8A8690]">Loading course...</p>
        </div>
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <p className="text-[#1A1A2E] font-medium">{error || 'Course not found'}</p>
      </div>
    );
  }

  const totalLectures = course.chapters.reduce((sum, ch) => sum + ch.lectures.length, 0);

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link href="/courses" className="inline-flex items-center text-sm text-[#8A8690] hover:text-[#3B82F6] font-medium transition-colors">
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            All Courses
          </Link>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E5F1] p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-[#1A1A2E] tracking-tight mb-2" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                {course.course_title}
              </h1>
              <div className="flex items-center gap-4 text-xs text-[#8A8690]">
                <span className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
                  </svg>
                  {course.chapters.length} chapters
                </span>
                <span className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" />
                  </svg>
                  {totalLectures} lectures
                </span>
              </div>
            </div>
            <div className="w-2 h-12 rounded-full bg-gradient-to-b from-[#3B82F6] to-[#2563EB]"></div>
          </div>
        </div>

        <div className="space-y-3">
          {course.chapters.map((chapter, index) => {
            const isExpanded = expandedChapters.has(chapter.chapter_title);
            return (
              <div key={chapter.chapter_title} className={`bg-white rounded-xl border transition-all duration-200 ${isExpanded ? 'border-[#3B82F6]/20 shadow-sm' : 'border-[#E2E5F1]'}`}>
                <button onClick={() => toggleChapter(chapter.chapter_title)} className="w-full px-5 py-4 text-left flex items-center justify-between">
                  <div className="flex items-center gap-3.5">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold transition-all ${isExpanded ? 'bg-[#3B82F6] text-white' : 'bg-[#EFF6FF] text-[#8A8690]'}`}>
                      {index + 1}
                    </div>
                    <div>
                      <h2 className={`text-sm font-semibold transition-colors ${isExpanded ? 'text-[#1A1A2E]' : 'text-[#1A1A2E]/80'}`} style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                        {chapter.chapter_title}
                      </h2>
                      <p className="text-[11px] text-[#8A8690] mt-0.5">{chapter.lectures.length} lecture{chapter.lectures.length !== 1 ? 's' : ''}</p>
                    </div>
                  </div>
                  <svg className={`w-4 h-4 text-[#8A8690] transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {isExpanded && (
                  <div className="px-5 pb-4 animate-fade-in">
                    <div className="border-t border-[#E2E5F1]/60 pt-2 space-y-0.5">
                      {chapter.lectures.map((lecture) => (
                        <Link key={lecture.lecture_id} href={`/courses/${courseId}/lectures/${lecture.lecture_id}`} className="group flex items-center justify-between px-3.5 py-2.5 rounded-lg hover:bg-[#EFF6FF] transition-colors">
                          <div className="flex items-center gap-3">
                            <div className="w-6 h-6 rounded-md bg-[#F3F6FF] group-hover:bg-[#3B82F6] flex items-center justify-center transition-colors">
                              <svg className="w-3 h-3 text-[#8A8690] group-hover:text-white transition-colors" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                            </div>
                            <span className="text-[13px] text-[#1A1A2E]/80 group-hover:text-[#1A1A2E] font-medium transition-colors">{lecture.lecture_title}</span>
                          </div>
                          {lecture.duration && (
                            <span className="text-[11px] text-[#8A8690] font-medium tabular-nums">{Math.floor(lecture.duration / 60)}:{(lecture.duration % 60).toString().padStart(2, '0')}</span>
                          )}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
