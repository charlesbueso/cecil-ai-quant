"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { LogIn, UserPlus, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();
  const router = useRouter();

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setSuccess(null);
      setLoading(true);

      try {
        if (mode === "login") {
          const { error } = await signIn(email, password);
          if (error) {
            setError(error);
          } else {
            router.push("/");
          }
        } else {
          const { error } = await signUp(email, password, displayName);
          if (error) {
            setError(error);
          } else {
            setSuccess(
              "Account created! Check your email for a confirmation link."
            );
          }
        }
      } finally {
        setLoading(false);
      }
    },
    [mode, email, password, displayName, signIn, signUp, router]
  );

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background relative">
      {/* Background video — full screen on mobile, left half on desktop */}
      <div className="absolute inset-0 z-0 md:relative md:w-1/2 overflow-hidden">
        <video
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          className="absolute inset-0 w-full h-full object-cover"
        >
          <source src="/videos/cecil-login.mp4" type="video/mp4" />
        </video>
        <div className="absolute inset-0 bg-black/50 md:bg-black/40" />
      </div>

      {/* Form panel — centered on mobile (over the bg), right half on desktop */}
      <div className="relative z-10 flex-1 flex items-center justify-center px-4 py-12 md:w-1/2 md:bg-background">
        {/* Subtle radial glow — desktop only */}
        <div className="hidden md:block absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(200,210,230,0.03)_0%,transparent_70%)]" />
        <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white tracking-tight">CECIL</h1>
          <p className="text-white/30 text-[11px] mt-1 uppercase tracking-[0.2em]">
            Financial Intelligence System
          </p>
        </div>

        {/* Form card */}
        <div className="rounded-2xl border border-white/[0.06] bg-surface/80 backdrop-blur-xl p-8 glow-border">
          <h2 className="text-lg font-semibold text-foreground mb-6">
            {mode === "login" ? "Welcome back" : "Create an account"}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-sm font-medium text-muted mb-1.5">
                  Display Name
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06]"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-white/40 mb-1.5">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06]"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/40 mb-1.5">
                Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06]"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-error/10 border border-error/20 px-4 py-3 text-sm text-error">
                {error}
              </div>
            )}

            {success && (
              <div className="rounded-lg bg-success/10 border border-success/20 px-4 py-3 text-sm text-success">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-white/[0.1] text-white py-3 text-sm font-medium hover:bg-white/[0.15] border border-white/[0.08] transition-all glow-border-hover disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : mode === "login" ? (
                <LogIn className="w-4 h-4" />
              ) : (
                <UserPlus className="w-4 h-4" />
              )}
              {loading
                ? "Please wait..."
                : mode === "login"
                ? "Sign In"
                : "Create Account"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setError(null);
                setSuccess(null);
              }}
              className="text-sm text-white/30 hover:text-white/60 transition-colors cursor-pointer"
            >
              {mode === "login"
                ? "Don't have an account? Sign up"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
