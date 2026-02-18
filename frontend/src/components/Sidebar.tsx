"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  User,
  Hexagon,
  Menu,
  X,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";

const NAV_ITEMS = [
  { href: "/chat", label: "Research Chat", icon: MessageSquare },
  { href: "/conversations", label: "Conversations", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, signOut } = useAuth();

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <>
      {/* Mobile hamburger button — fixed top-left */}
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 flex items-center justify-center w-10 h-10 rounded-lg bg-surface/80 backdrop-blur border border-white/[0.08] text-white/70 hover:text-white transition-colors cursor-pointer"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile backdrop overlay */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          onClick={closeMobile}
        />
      )}

      {/* Sidebar — desktop: normal flow; mobile: fixed overlay drawer */}
      <aside
        className={`
          relative flex flex-col transition-all duration-300 overflow-hidden
          /* Desktop */
          max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:w-72 max-md:shadow-2xl
          ${mobileOpen ? "max-md:translate-x-0" : "max-md:-translate-x-full"}
          /* Desktop collapsed/expanded */
          md:relative ${collapsed ? "md:w-16" : "md:w-64"}
        `}
      >
        {/* Background image layer */}
        <div
          className="absolute inset-0 bg-cover bg-center bg-no-repeat"
          style={{ backgroundImage: "url('/images/sidebar-bg.jpg')" }}
        />
        {/* Dark overlay on image */}
        <div className="absolute inset-0 bg-black/75" />
        {/* Glass frost layer */}
        <div className="absolute inset-0 glass" />
        {/* Scanline overlay */}
        <div className="absolute inset-0 scanline" />
        {/* Right edge glow line */}
        <div className="absolute top-0 right-0 w-px h-full bg-gradient-to-b from-transparent via-white/10 to-transparent" />

      {/* Content layer */}
      <div className="relative z-10 flex flex-col h-full">
        {/* Logo */}
        <div
          className="flex items-center gap-3 px-4 py-5 border-b border-white/[0.06] cursor-pointer hover:bg-white/[0.04]"
          onClick={() => { if (window.innerWidth >= 768) setCollapsed(!collapsed); }}
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.08] glow-border">
            <Hexagon className="w-5 h-5 text-white/80" />
          </div>
          {/* Show label on mobile always, on desktop only when expanded */}
          <div className={`${collapsed ? "hidden max-md:block" : ""}`}>
            <h1 className="text-lg font-bold text-white tracking-tight">
              CECIL
            </h1>
            <p className="text-[10px] text-white/40 uppercase tracking-[0.2em]">
              Financial Intelligence
            </p>
          </div>
          {/* Mobile close button */}
          <button
            onClick={(e) => { e.stopPropagation(); closeMobile(); }}
            className="md:hidden ml-auto p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href === "/chat" && pathname === "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-white/[0.1] text-white glow-border"
                    : "text-white/40 hover:text-white/80 hover:bg-white/[0.05]"
                }`}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {/* Show label on mobile always, on desktop only when expanded */}
                <span className={`${collapsed ? "hidden max-md:inline" : ""}`}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Agent status badges */}
        {(!collapsed || mobileOpen) && (
          <div className="px-4 py-3 border-t border-white/[0.06]">
            <p className="text-[10px] font-medium text-white/30 mb-2 uppercase tracking-[0.15em]">
              Agents
            </p>
            <div className="space-y-1.5">
              {[
                { name: "Quant", color: "bg-cyan" },
                { name: "Portfolio", color: "bg-success" },
                { name: "Research", color: "bg-warning" },
              ].map((agent) => (
                <div key={agent.name} className="flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full ${agent.color} animate-breathe`} />
                  <span className="text-xs text-white/40">{agent.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* User info & logout */}
        <div className="px-3 py-3 border-t border-white/[0.06]">
          {(!collapsed || mobileOpen) ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-white/[0.08] flex-shrink-0">
                <User className="w-4 h-4 text-white/60" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white/80 truncate">
                  {user?.user_metadata?.display_name || user?.email?.split("@")[0]}
                </p>
                <p className="text-[10px] text-white/30 truncate">{user?.email}</p>
              </div>
              <button
                onClick={() => signOut()}
                className="p-1.5 rounded-lg text-white/30 hover:text-error hover:bg-error/10 transition-colors cursor-pointer"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => signOut()}
              className="flex items-center justify-center w-full p-2 rounded-lg text-white/30 hover:text-error hover:bg-error/10 transition-colors cursor-pointer"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Collapse toggle — desktop only */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`hidden md:flex items-center py-3 border-t border-white/[0.06] text-white/30 hover:text-white/70 transition-colors cursor-pointer ${
            collapsed ? "justify-center" : "justify-end pr-4"
          }`}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
    </>
  );
}
