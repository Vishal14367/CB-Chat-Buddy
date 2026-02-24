import Link from 'next/link';

/**
 * Custom 404 page for Next.js App Router.
 * Rendered whenever notFound() is called or a route segment is missing.
 */
export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* 404 number */}
        <p className="text-[80px] font-black text-[#E2E5F1] leading-none mb-4 select-none" aria-hidden="true">
          404
        </p>

        {/* Icon */}
        <div className="w-16 h-16 bg-[#EFF6FF] rounded-2xl flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
          </svg>
        </div>

        <h1 className="text-[22px] font-bold text-[#1A1A2E] mb-2" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
          Page not found
        </h1>
        <p className="text-[14px] text-[#8A8690] mb-8 leading-relaxed">
          Hmm, this page doesn&apos;t exist. The lecture or course you&apos;re looking for may have moved or been removed.
        </p>

        <Link
          href="/courses"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#3B82F6] text-white text-[13px] font-semibold rounded-xl hover:bg-[#2563EB] transition-colors focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:ring-offset-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Browse courses
        </Link>
      </div>
    </div>
  );
}
