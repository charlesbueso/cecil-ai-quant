"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { loading, user } = useAuth();

  // Redirect to login when user signs out
  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [loading, user, pathname, router]);

  // Show loading spinner during auth check
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-10 h-10 border border-white/10 rounded-lg flex items-center justify-center glow-accent">
              <Loader2 className="w-5 h-5 text-white/70 animate-spin" />
            </div>
          </div>
          <p className="text-[10px] text-white/20 uppercase tracking-[0.3em]">Initializing</p>
        </div>
      </div>
    );
  }

  // Login page – no sidebar
  if (pathname === "/login" || !user) {
    return <>{children}</>;
  }

  // Authenticated layout with sidebar
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto min-w-0">{children}</main>
    </div>
  );
}
