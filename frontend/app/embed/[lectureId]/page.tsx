'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { LectureDetail } from '@/types';
import ChatPanel from '@/components/ChatPanel';

export default function EmbedPage() {
  const params = useParams();
  const lectureId = params.lectureId as string;

  const [lecture, setLecture] = useState<LectureDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#FAFAFB]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[#8A8690]">Loading...</span>
        </div>
      </div>
    );
  }

  if (error || !lecture) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#FAFAFB]">
        <div className="text-center px-6">
          <p className="text-[#E34850] text-sm font-medium">{error || 'Lecture not found'}</p>
          <p className="text-[#8A8690] text-xs mt-1">Check the lecture ID and try again.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen">
      <ChatPanel
        lectureId={lectureId}
        courseTitle={lecture.course_title}
        currentLectureOrder={lecture.lecture_order ?? 0}
      />
    </div>
  );
}
