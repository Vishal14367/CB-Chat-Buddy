import type { Metadata } from "next";
import "../../globals.css";

export const metadata: Metadata = {
  title: "Chat Buddy",
  description: "AI-powered lecture assistant by Codebasics",
};

export default function EmbedLayout({
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
      <body className="antialiased m-0 p-0 overflow-hidden" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
