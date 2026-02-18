"use client";

import { Crown, BarChart3, Briefcase, Newspaper, Code2 } from "lucide-react";

const ICON_MAP: Record<string, React.ElementType> = {
  crown: Crown,
  "bar-chart-3": BarChart3,
  briefcase: Briefcase,
  newspaper: Newspaper,
  "code-2": Code2,
};

interface AgentBadgeProps {
  agent: string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  active?: boolean;
}

const AGENT_META: Record<
  string,
  { name: string; color: string; icon: string }
> = {
  project_manager: { name: "Project Manager", color: "#d0d4dc", icon: "crown" },
  quant_researcher: { name: "Quant Researcher", color: "#7dd3fc", icon: "bar-chart-3" },
  portfolio_analyst: { name: "Portfolio Analyst", color: "#86efac", icon: "briefcase" },
  research_intelligence: { name: "Research Intel", color: "#fde68a", icon: "newspaper" },
};

export default function AgentBadge({
  agent,
  size = "md",
  showLabel = true,
  active = false,
}: AgentBadgeProps) {
  const meta = AGENT_META[agent] || {
    name: agent,
    color: "#71717a",
    icon: "code-2",
  };
  const Icon = ICON_MAP[meta.icon] || Code2;

  const sizeClasses = {
    sm: "w-5 h-5 text-xs",
    md: "w-7 h-7 text-sm",
    lg: "w-9 h-9 text-base",
  };

  const iconSizes = {
    sm: "w-3 h-3",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex items-center justify-center rounded-lg ${sizeClasses[size]} ${
          active ? "animate-pulse-glow" : ""
        }`}
        style={{
          backgroundColor: `${meta.color}20`,
          color: meta.color,
        }}
      >
        <Icon className={iconSizes[size]} />
      </div>
      {showLabel && (
        <span
          className="font-medium"
          style={{ color: meta.color }}
        >
          {meta.name}
        </span>
      )}
    </div>
  );
}
