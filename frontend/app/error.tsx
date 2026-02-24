'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js App Router error boundary.
 * Catches unhandled runtime errors in child route segments
 * and shows a branded recovery screen instead of a blank page.
 */
export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log to console (swap for an error-reporting service like Sentry in production)
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>

        <h1 className="text-[22px] font-bold text-[#1A1A2E] mb-2" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
          Something went wrong
        </h1>
        <p className="text-[14px] text-[#8A8690] mb-8 leading-relaxed">
          An unexpected error occurred. Don&apos;t worry — your progress is safe. Try refreshing the page or go back to your courses.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={reset}
            className="px-5 py-2.5 bg-[#3B82F6] text-white text-[13px] font-semibold rounded-xl hover:bg-[#2563EB] transition-colors focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:ring-offset-2"
          >
            Try again
          </button>
          <Link
            href="/courses"
            className="px-5 py-2.5 bg-[#F4F4F8] text-[#1A1A2E] text-[13px] font-semibold rounded-xl hover:bg-[#E2E5F1] transition-colors focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:ring-offset-2"
          >
            Back to courses
          </Link>
        </div>
      </div>
    </div>
  );
}
