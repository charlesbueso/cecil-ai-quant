"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  ExternalLink,
  Calendar,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { getReports, getReportHtml, type ReportInfo } from "@/lib/api";

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getReports();
      setReports(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const openReport = useCallback(async (filename: string) => {
    setSelectedReport(filename);
    setLoadingReport(true);
    try {
      const html = await getReportHtml(filename);
      setReportHtml(html);
    } catch {
      setReportHtml(
        "<p style='padding:20px;color:#ef4444;'>Failed to load report</p>"
      );
    } finally {
      setLoadingReport(false);
    }
  }, []);

  const filteredReports = reports.filter(
    (r) =>
      r.task.toLowerCase().includes(search.toLowerCase()) ||
      r.filename.toLowerCase().includes(search.toLowerCase())
  );

  // Report viewer overlay
  if (selectedReport && reportHtml) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-3 px-4 sm:px-6 py-3 sm:py-4 border-b border-white/[0.06] bg-surface/60 backdrop-blur-sm pl-14 md:pl-6">
          <button
            onClick={() => {
              setSelectedReport(null);
              setReportHtml(null);
            }}
            className="flex items-center gap-1.5 text-sm text-white/40 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
            Close
          </button>
          <span className="text-sm font-medium text-foreground truncate">
            {selectedReport}
          </span>
        </div>
        <div className="flex-1">
          {loadingReport ? (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-5 h-5 text-white/40 animate-spin" />
            </div>
          ) : (
            <iframe
              srcDoc={reportHtml}
              className="w-full h-full bg-white"
              title={selectedReport}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto pt-16 md:pt-6">
      <div className="flex items-center justify-between mb-5 sm:mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-foreground">Reports</h1>
          <p className="text-xs sm:text-sm text-muted mt-1">
            Previously generated analysis reports
          </p>
        </div>
        <button
          onClick={fetchReports}
          disabled={loading}
          className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-2 rounded-lg border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-sm text-white/40 hover:text-white/80 transition-all disabled:opacity-50"
        >
          <RefreshCw
            className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
          />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-5 sm:mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search reports..."
          className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-white/[0.06] bg-white/[0.03] text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:border-white/[0.12]"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 px-4 py-3 rounded-lg bg-error/10 border border-error/20 text-sm text-error">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-lg bg-white/[0.02] border border-white/[0.04] animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredReports.length === 0 && (
        <div className="text-center py-16">
          <FileText className="w-12 h-12 text-muted/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted mb-1">
            {search ? "No matching reports" : "No reports yet"}
          </h3>
          <p className="text-sm text-muted">
            {search
              ? "Try a different search term"
              : "Reports will appear here after running analyses"}
          </p>
        </div>
      )}

      {/* Reports list */}
      {!loading && filteredReports.length > 0 && (
        <div className="space-y-3">
          {filteredReports.map((report) => (
            <button
              key={report.filename}
              onClick={() => openReport(report.filename)}
              className="w-full text-left flex items-center gap-3 sm:gap-4 px-3 sm:px-5 py-3 sm:py-4 rounded-xl border border-white/[0.04] bg-white/[0.02] hover:border-white/[0.1] hover:bg-white/[0.04] transition-all group glow-border-hover"
            >
              <div className="hidden sm:flex items-center justify-center w-10 h-10 rounded-lg bg-white/[0.04]">
                <FileText className="w-5 h-5 text-white/50" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-foreground group-hover:text-white transition-colors truncate">
                  {report.task}
                </h3>
                <div className="flex items-center gap-2 sm:gap-3 mt-1 flex-wrap">
                  <span className="flex items-center gap-1 text-xs text-muted">
                    <Calendar className="w-3 h-3" />
                    {new Date(report.created_at).toLocaleDateString()}
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-xs bg-white/[0.04] text-white/30 uppercase">
                    {report.type}
                  </span>
                </div>
              </div>
              <ExternalLink className="w-4 h-4 text-white/20 group-hover:text-white/60 transition-colors" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
