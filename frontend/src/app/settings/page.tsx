"use client";

import { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Wifi,
  WifiOff,
  Brain,
  Database,
  TrendingUp,
} from "lucide-react";
import { getHealth, type HealthResponse } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const LLM_LABELS: Record<string, string> = {
  groq: "Groq",
  together: "Together AI",
  fireworks: "Fireworks AI",
  openrouter: "OpenRouter",
};

const DATA_LABELS: Record<string, { name: string; note: string }> = {
  fred: { name: "FRED", note: "Economic data" },
  fmp: { name: "Financial Modeling Prep", note: "Financials & ratios" },
  finnhub: { name: "Finnhub", note: "Real-time market data" },
  alpha_vantage: { name: "Alpha Vantage", note: "Stock & forex data" },
  news_api: { name: "NewsAPI", note: "News headlines" },
};

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const { user } = useAuth();

  const refresh = () => {
    setLoading(true);
    setError(false);
    getHealth()
      .then(setHealth)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const llmCount = health
    ? Object.values(health.providers).filter(Boolean).length
    : 0;
  const dataCount = health?.data_providers
    ? Object.values(health.data_providers).filter(Boolean).length
    : 0;

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto pt-16 md:pt-6">
      <div className="mb-6 sm:mb-8">
        <h1 className="text-xl sm:text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-xs sm:text-sm text-muted mt-1">
          System status and connected services
        </p>
      </div>

      {/* Connection Status */}
      <section className="mb-6">
        <div className="rounded-xl border border-white/[0.06] bg-surface/60 p-4 sm:p-5 glow-border">
          {loading ? (
            <div className="flex items-center gap-3 text-sm text-muted">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Checking connection...
            </div>
          ) : error ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-error/10">
                  <WifiOff className="w-5 h-5 text-error" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Cannot reach server
                  </p>
                  <p className="text-xs text-muted">
                    The backend API is not responding
                  </p>
                </div>
              </div>
              <button
                onClick={refresh}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/[0.04] text-white/40 hover:text-white/80 border border-white/[0.06] transition-colors"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-success/10">
                  <Wifi className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Connected
                  </p>
                  <p className="text-xs text-muted">
                    Cecil AI v{health?.version} is running
                  </p>
                </div>
              </div>
              <button
                onClick={refresh}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/[0.04] text-white/40 hover:text-white/80 border border-white/[0.06] transition-colors"
              >
                Refresh
              </button>
            </div>
          )}
        </div>
      </section>

      {health && (
        <>
          {/* AI Models */}
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-4 h-4 text-white/60" />
              <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                AI Models
              </h2>
              <span className="text-xs text-muted ml-auto">
                {llmCount} connected
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(health.providers).map(
                ([id, connected]) => (
                  <div
                    key={id}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
                      connected
                        ? "border-success/20 bg-success/5"
                        : "border-white/[0.04] bg-white/[0.02]"
                    }`}
                  >
                    {connected ? (
                      <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-white/20 flex-shrink-0" />
                    )}
                    <span
                      className={`text-sm font-medium ${
                        connected ? "text-foreground" : "text-muted"
                      }`}
                    >
                      {LLM_LABELS[id] || id}
                    </span>
                  </div>
                )
              )}
            </div>
          </section>

          {/* Data Sources */}
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-4 h-4 text-white/60" />
              <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                Data Sources
              </h2>
              <span className="text-xs text-muted ml-auto">
                {dataCount} connected
              </span>
            </div>

            {/* Always available */}
            <div className="mb-2">
              <p className="text-xs text-muted mb-1.5">Always available</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  { name: "Yahoo Finance", note: "Stocks, options, crypto" },
                  { name: "Google News", note: "Headlines & sentiment" },
                ].map((src) => (
                  <div key={src.name} className="flex items-center gap-3 px-4 py-3 rounded-xl border border-success/20 bg-success/5">
                    <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
                    <div>
                      <span className="text-sm font-medium text-foreground">
                        {src.name}
                      </span>
                      <p className="text-xs text-muted">{src.note}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* API key dependent */}
            {health.data_providers &&
              Object.keys(health.data_providers).length > 0 && (
                <div>
                  <p className="text-xs text-muted mb-1.5">Optional (API key required)</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Object.entries(health.data_providers).map(
                      ([id, connected]) => {
                        const info = DATA_LABELS[id] || {
                          name: id,
                          note: "",
                        };
                        return (
                          <div
                            key={id}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
                              connected
                                ? "border-success/20 bg-success/5"
                                : "border-white/[0.04] bg-white/[0.02]"
                            }`}
                          >
                            {connected ? (
                              <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
                            ) : (
                              <AlertCircle className="w-4 h-4 text-white/20 flex-shrink-0" />
                            )}
                            <div>
                              <span
                                className={`text-sm font-medium ${
                                  connected
                                    ? "text-foreground"
                                    : "text-muted"
                                }`}
                              >
                                {info.name}
                              </span>
                              {info.note && (
                                <p className="text-xs text-muted">
                                  {info.note}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              )}
          </section>

          {/* Agents */}
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-white/60" />
              <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                Research Agents
              </h2>
            </div>
            <div className="space-y-2">
              {[
                {
                  name: "Quant Researcher",
                  desc: "Stock prices, technicals, statistical analysis",
                  color: "#06b6d4",
                },
                {
                  name: "Portfolio Analyst",
                  desc: "Risk metrics, factor screening, valuations",
                  color: "#22c55e",
                },
                {
                  name: "Research Intelligence",
                  desc: "News, macro data, market sentiment",
                  color: "#eab308",
                },
              ].map((agent) => (
                <div
                  key={agent.name}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/[0.04] bg-white/[0.02]"
                >
                  <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: agent.color }}
                  />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {agent.name}
                    </p>
                    <p className="text-xs text-muted">{agent.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {/* Account */}
      {user && (
        <section>
          <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider mb-3">
            Account
          </h2>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
            <p className="text-sm text-foreground">
              {user.user_metadata?.display_name || user.email?.split("@")[0]}
            </p>
            <p className="text-xs text-muted">{user.email}</p>
          </div>
        </section>
      )}
    </div>
  );
}
