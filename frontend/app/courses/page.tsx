'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Course } from '@/types';
import Link from 'next/link';

// ---- Category config: label, colors, and SVG icon per category ----
const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  'Data & Analytics':  { label: 'Data & Analytics',  color: 'text-[#3B82F6]', bg: 'bg-[#EFF6FF]' },
  'Programming':       { label: 'Programming',       color: 'text-[#6366F1]', bg: 'bg-[#EEF2FF]' },
  'AI & Data Science': { label: 'AI & Data Science', color: 'text-[#8B5CF6]', bg: 'bg-[#F5F3FF]' },
  'AI & Automation':   { label: 'AI & Automation',   color: 'text-[#F89937]', bg: 'bg-[#FFF4E6]' },
  'Data Engineering':  { label: 'Data Engineering',  color: 'text-[#0D9488]', bg: 'bg-[#F0FDFA]' },
  'Soft Skills':       { label: 'Soft Skills',       color: 'text-[#10B981]', bg: 'bg-[#ECFDF5]' },
  'Career':            { label: 'Career',            color: 'text-[#64748B]', bg: 'bg-[#F8FAFC]' },
  'Projects':          { label: 'Projects',          color: 'text-[#D97706]', bg: 'bg-[#FFFBEB]' },
  'Live Sessions':     { label: 'Live Sessions',     color: 'text-[#E11D48]', bg: 'bg-[#FFF1F2]' },
  'Welcome':           { label: 'Welcome',           color: 'text-[#0EA5E9]', bg: 'bg-[#F0F9FF]' },
  'Course':            { label: 'Course',            color: 'text-[#3B82F6]', bg: 'bg-[#EFF6FF]' },
};

const DEFAULT_CATEGORY = CATEGORY_CONFIG['Course'];

function getCourseCategory(course: Course): { label: string; color: string; bg: string } {
  if (course.category && CATEGORY_CONFIG[course.category]) {
    return CATEGORY_CONFIG[course.category];
  }
  // Keyword fallback for courses not yet in the backend catalog
  const t = course.course_title.toLowerCase();
  if (t.includes('power bi') || t.includes('excel') || t.includes('tableau') || t.includes('fabric') || t.includes('da 2.0'))
    return CATEGORY_CONFIG['Data & Analytics'];
  if (t.includes('python') || t.includes('sql'))
    return CATEGORY_CONFIG['Programming'];
  if (t.includes('machine learning') || t.includes('deep learning') || t.includes('math and statistics') || t.includes('nlp'))
    return CATEGORY_CONFIG['AI & Data Science'];
  if (t.includes('ai automation') || t.includes('gen ai') || t.includes('ai toolkit') || t.includes('agentic'))
    return CATEGORY_CONFIG['AI & Automation'];
  if (t.includes('data engineering') || t.includes('spark') || t.includes('snowflake') || t.includes('airflow') || t.includes('kafka'))
    return CATEGORY_CONFIG['Data Engineering'];
  if (t.includes('communication') || t.includes('time management') || t.includes('personal branding'))
    return CATEGORY_CONFIG['Soft Skills'];
  if (t.includes('project') || t.includes('case stud'))
    return CATEGORY_CONFIG['Projects'];
  if (t.includes('interview') || t.includes('job') || t.includes('credibility') || t.includes('resume') || t.includes('internship'))
    return CATEGORY_CONFIG['Career'];
  if (t.includes('webinar') || t.includes('live'))
    return CATEGORY_CONFIG['Live Sessions'];
  if (t.includes('welcome') || t.includes('bootcamp experience'))
    return CATEGORY_CONFIG['Welcome'];
  return DEFAULT_CATEGORY;
}

// Icon per category key
function getCategoryIcon(categoryKey: string) {
  switch (categoryKey) {
    case 'Data & Analytics':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      );
    case 'Programming':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
        </svg>
      );
    case 'AI & Data Science':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
        </svg>
      );
    case 'AI & Automation':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
      );
    case 'Data Engineering':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
        </svg>
      );
    case 'Soft Skills':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
      );
    case 'Career':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
        </svg>
      );
    case 'Projects':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.42 15.17l-5.1-3.06a.75.75 0 010-1.28l5.1-3.06a.75.75 0 01.76 0l5.1 3.06a.75.75 0 010 1.28l-5.1 3.06a.75.75 0 01-.76 0zM3.75 12l7.67 4.6 7.67-4.6M3.75 16.5l7.67 4.6 7.67-4.6" />
        </svg>
      );
    case 'Live Sessions':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
      );
    case 'Welcome':
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
        </svg>
      );
    default:
      return (
        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      );
  }
}

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadCourses() {
      try {
        const data = await api.getCourses();
        setCourses(data);
      } catch (err) {
        setError('Failed to load courses');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadCourses();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-7 h-7 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-[#8A8690]">Loading courses...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
        <div className="text-center">
          <p className="text-[#1A1A2E] font-medium">{error}</p>
          <button onClick={() => window.location.reload()} className="mt-2 text-sm text-[#3B82F6] font-medium hover:underline">
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[#1A1A2E] tracking-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
            My Courses
          </h1>
          <p className="text-sm text-[#8A8690] mt-1">
            Select a course to start learning with your AI buddy
          </p>
          <p className="text-xs text-[#8A8690]/60 mt-0.5">
            {courses.length} courses available
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course) => {
            const category = getCourseCategory(course);
            const categoryKey = course.category || category.label;
            return (
              <Link
                key={course.course_id}
                href={`/courses/${course.course_id}`}
                className="group bg-white rounded-xl p-5 border border-[#E2E5F1] hover:border-[#3B82F6]/30 hover:shadow-md hover:shadow-[#3B82F6]/5 transition-all duration-200"
              >
                {/* Category badge + icon */}
                <div className="flex items-center justify-between mb-3.5">
                  <div className={`w-9 h-9 rounded-lg ${category.bg} flex items-center justify-center group-hover:bg-[#3B82F6] transition-colors`}>
                    <span className={`${category.color} group-hover:text-white transition-colors`}>
                      {getCategoryIcon(categoryKey)}
                    </span>
                  </div>
                  <span className={`text-[10px] font-medium ${category.color} ${category.bg} px-2 py-0.5 rounded-full`}>
                    {category.label}
                  </span>
                </div>

                <h2 className="text-[15px] font-semibold text-[#1A1A2E] mb-1.5 leading-snug group-hover:text-[#3B82F6] transition-colors" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                  {course.course_title}
                </h2>

                {/* Chapter/Lecture counts */}
                <div className="flex items-center gap-3 mt-2">
                  {course.chapter_count != null && (
                    <span className="text-[11px] text-[#8A8690] flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                      </svg>
                      {course.chapter_count} chapters
                    </span>
                  )}
                  {course.lecture_count != null && (
                    <span className="text-[11px] text-[#8A8690] flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                      {course.lecture_count} lectures
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-center text-xs font-medium text-[#3B82F6] opacity-0 group-hover:opacity-100 transition-opacity">
                  <span>Open course</span>
                  <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
