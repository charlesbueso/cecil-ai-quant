"use client";

import AgentBadge from "./AgentBadge";

interface AgentStep {
  agent: string;
  summary?: string;
  tool_calls?: number;
  iteration?: number;
}

interface AgentFlowVisualizerProps {
  steps: AgentStep[];
  activeAgent?: string;
}

export default function AgentFlowVisualizer({
  steps,
  activeAgent,
}: AgentFlowVisualizerProps) {
  if (steps.length === 0) return null;

  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-surface/60 rounded-lg border border-white/[0.06] overflow-x-auto glow-border">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center">
          <div
            className={`transition-all ${
              step.agent === activeAgent ? "scale-110" : ""
            }`}
          >
            <AgentBadge
              agent={step.agent}
              size="sm"
              showLabel={false}
              active={step.agent === activeAgent}
            />
          </div>
          {i < steps.length - 1 && (
            <div className="w-6 h-px bg-white/10 mx-1" />
          )}
        </div>
      ))}
      {activeAgent && (
        <div className="ml-3 flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-white/60 animate-pulse" />
          <span className="text-xs text-white/30 whitespace-nowrap font-mono tracking-wider">
            PROCESSING
          </span>
        </div>
      )}
    </div>
  );
}
