"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Trash2,
  Plus,
  Search,
  Loader2,
  Calendar,
} from "lucide-react";
import {
  getConversations,
  deleteConversation,
  type Conversation,
} from "@/lib/api";

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const router = useRouter();

  useEffect(() => {
    getConversations()
      .then((convos) => {
        setConversations(convos);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
    } catch {
      // silently fail
    }
  }, []);

  const handleOpen = useCallback(
    (id: string) => {
      router.push(`/chat?conversation=${id}`);
    },
    [router]
  );

  const filtered = search
    ? conversations.filter((c) =>
        (c.title || "").toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  // Group by date
  const grouped = filtered.reduce<Record<string, Conversation[]>>(
    (acc, convo) => {
      const date = new Date(convo.updated_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
      if (!acc[date]) acc[date] = [];
      acc[date].push(convo);
      return acc;
    },
    {}
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 pt-16 md:pt-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-5 sm:mb-6">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-foreground">
              Conversations
            </h1>
            <p className="text-xs sm:text-sm text-muted mt-1">
              {conversations.length} conversation
              {conversations.length !== 1 ? "s" : ""}
            </p>
          </div>
          <button
            onClick={() => router.push("/chat")}
            className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl bg-white/[0.08] text-white text-sm font-medium hover:bg-white/[0.12] border border-white/[0.06] transition-all glow-border-hover cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Chat</span>
            <span className="sm:hidden">New</span>
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-5 sm:mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-white/[0.06] bg-white/[0.03] text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12] focus:ring-1 focus:ring-white/[0.06]"
          />
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-white/40 animate-spin" />
          </div>
        )}

        {/* Empty state */}
        {!loading && conversations.length === 0 && (
          <div className="text-center py-20">
            <MessageSquare className="w-12 h-12 text-muted mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-foreground mb-2">
              No conversations yet
            </h2>
            <p className="text-sm text-muted mb-6">
              Start a research chat to see your history here.
            </p>
            <button
              onClick={() => router.push("/chat")}
              className="px-4 py-2 rounded-xl bg-white/[0.08] text-white text-sm font-medium hover:bg-white/[0.12] border border-white/[0.06] transition-all"
            >
              Start Research
            </button>
          </div>
        )}

        {/* No search results */}
        {!loading && conversations.length > 0 && filtered.length === 0 && (
          <div className="text-center py-12">
            <p className="text-sm text-muted">
              No conversations matching &ldquo;{search}&rdquo;
            </p>
          </div>
        )}

        {/* Conversation list grouped by date */}
        {Object.entries(grouped).map(([date, convos]) => (
          <div key={date} className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-3.5 h-3.5 text-muted" />
              <h3 className="text-xs font-medium text-muted uppercase tracking-wider">
                {date}
              </h3>
            </div>
            <div className="space-y-1">
              {convos.map((convo) => (
                <div
                  key={convo.id}
                  className="flex items-center justify-between group px-3 sm:px-4 py-3 rounded-xl border border-white/[0.04] bg-white/[0.02] hover:border-white/[0.1] hover:bg-white/[0.04] transition-all cursor-pointer glow-border-hover"
                  onClick={() => handleOpen(convo.id)}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <MessageSquare className="w-4 h-4 text-muted flex-shrink-0 hidden sm:block" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {convo.title || "Untitled conversation"}
                      </p>
                      <p className="text-xs text-muted">
                        {new Date(convo.updated_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(convo.id);
                    }}
                    className="md:opacity-0 md:group-hover:opacity-100 p-2 sm:p-1.5 rounded-lg text-muted hover:text-error hover:bg-error/10 transition-all cursor-pointer flex-shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
