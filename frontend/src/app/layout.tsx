import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import AppShell from "@/components/AppShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Cecil AI – Financial Research",
  description: "Multi-agent financial research system powered by AI",
  icons: {
    icon: '/images/favicon.ico',
  },
  openGraph: {
    title: "Cecil AI – Financial Research",
    description: "Multi-agent financial research system powered by AI",
    images: ['/images/page-metadata.jpg'],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: "Cecil AI – Financial Research",
    description: "Multi-agent financial research system powered by AI",
    images: ['/images/page-metadata.jpg'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
