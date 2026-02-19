import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import Image from "next/image";

export const metadata: Metadata = {
  title: "Codebasics Chat Buddy",
  description: "AI-powered lecture assistant by Codebasics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body className="antialiased" suppressHydrationWarning>
        <nav className="sticky top-0 z-40 w-full bg-white border-b border-[#E2E5F1]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-14">
              <Link href="/courses" className="flex items-center space-x-2.5 group">
                <Image
                  src="/logo.png"
                  alt="Codebasics"
                  width={30}
                  height={30}
                  className="object-contain"
                />
                <div className="flex items-center gap-1.5">
                  <span className="text-[#1A1A2E] font-bold text-[17px] tracking-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                    Codebasics
                  </span>
                  <span className="text-[#3B82F6] font-semibold text-[15px] tracking-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>
                    Chat Buddy
                  </span>
                </div>
              </Link>
              <div className="flex items-center space-x-1">
                <Link
                  href="/courses"
                  className="px-3 py-1.5 rounded-lg text-[#8A8690] hover:text-[#3B82F6] hover:bg-[#EFF6FF] text-[13px] font-medium transition-all"
                >
                  Courses
                </Link>
                <Link
                  href="/profile"
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[#8A8690] hover:text-[#3B82F6] hover:bg-[#EFF6FF] text-[13px] font-medium transition-all"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>Settings</span>
                </Link>
              </div>
            </div>
          </div>
        </nav>
        <main className="min-h-[calc(100vh-56px)]">
          {children}
        </main>
      </body>
    </html>
  );
}
