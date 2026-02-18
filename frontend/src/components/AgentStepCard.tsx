"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import AgentBadge from "./AgentBadge";
import MarkdownRenderer from "./MarkdownRenderer";
import type { AgentStep } from "@/lib/api";

interface AgentStepCardProps {
  step: AgentStep;
  index: number;
  isActive?: boolean;
}

export default function AgentStepCard({
  step,
  index,
  isActive = false,
}: AgentStepCardProps) {
  // Start expanded if this step is currently active (live streaming)
  const [expanded, setExpanded] = useState(isActive);

  // For collapsed view, show a brief preview of the summary
  const preview = step.summary
    ? step.summary.replace(/\*\*/g, "").replace(/\*/g, "").slice(0, 120) +
      (step.summary.length > 120 ? "…" : "")
    : "";

  return (
    <div
      className={`rounded-lg border transition-all ${
        isActive
          ? "border-white/[0.1] bg-white/[0.03] glow-border"
          : "border-white/[0.04] bg-surface/60 hover:border-white/[0.08]"
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center w-full gap-3 px-4 py-3 text-left"
      >
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-white/[0.04] text-xs font-mono text-white/30 border border-white/[0.06]">
          {index + 1}
        </span>

        <AgentBadge agent={step.agent} size="sm" />

        {/* Brief preview when collapsed */}
        {!expanded && preview && (
          <span className="flex-1 text-xs text-muted truncate max-w-[40%]">
            {preview}
          </span>
        )}

        <div className="flex items-center gap-2 ml-auto text-xs text-muted">
          {step.tool_calls > 0 && (
            <span className="flex items-center gap-1">
              <Wrench className="w-3 h-3" />
              {step.tool_calls} tools
            </span>
          )}
          <span
            className={`px-2 py-0.5 rounded-full text-xs ${
              step.status === "completed"
                ? "bg-success/10 text-success"
                : step.status === "failed"
                ? "bg-error/10 text-error"
                : "bg-warning/10 text-warning"
            }`}
          >
            {step.status}
          </span>
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>
      </button>

      {expanded && step.summary && (
        <div className="px-4 pb-4 pt-1 border-t border-border">
          <MarkdownRenderer content={step.summary} />
        </div>
      )}
    </div>
  );
}
