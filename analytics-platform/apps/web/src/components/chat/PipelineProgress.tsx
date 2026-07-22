import { CheckCircle, Circle, Loader2, XCircle } from "lucide-react";
import React from "react";

// The timeline stages are fixed by the backend to ensure a stable visual order.
const STAGE_ORDER = [
  "parsing_question",
  "resolving_entities",
  "planning_query",
  "generating_sql",
  "executing_query",
  "generating_insights",
];

export interface TraceEntry {
  stage: string;
  label: string;
  status: "in_progress" | "complete" | "error";
  at: string;
}

interface PipelineProgressProps {
  trace?: TraceEntry[] | null;
  className?: string;
}

export function PipelineProgress({ trace, className = "" }: PipelineProgressProps) {
  // If there's no trace yet or it's a non-analytics route (e.g. 'responding'), 
  // fallback to a generic spinner for that single entry or empty state.
  if (!trace || trace.length === 0) {
    return (
      <div className={`flex items-center space-x-2 text-sm text-gray-500 ${className}`}>
        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
        <span>Processing...</span>
      </div>
    );
  }

  // Handle single-stage non-analytics traces (greeting, help, conversation)
  if (trace.length === 1 && trace[0].stage === "responding") {
    return (
      <div className={`flex items-center space-x-2 text-sm text-gray-500 ${className}`}>
        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
        <span>{trace[0].label}</span>
      </div>
    );
  }

  // Handle analytics pipeline with multiple ordered stages
  return (
    <div className={`flex flex-col space-y-3 ${className}`}>
      {STAGE_ORDER.map((stageKey, idx) => {
        // Find if we have a trace entry for this stage
        const entry = trace.find((e) => e.stage === stageKey);
        
        // Find the "currently active" stage to pulse it. 
        // A stage is active if it's the last entry in the trace array and it's marked 'in_progress'.
        const isActive = entry && entry === trace[trace.length - 1] && entry.status === "in_progress";

        // Determine icon and text color based on status
        let Icon = Circle;
        let iconColor = "text-gray-200";
        let textColor = "text-gray-400"; // pending color
        let label = entry ? entry.label : getPendingLabel(stageKey);

        if (entry) {
          if (entry.status === "complete") {
            Icon = CheckCircle;
            iconColor = "text-emerald-500";
            textColor = "text-gray-700 font-medium";
          } else if (entry.status === "error") {
            Icon = XCircle;
            iconColor = "text-red-500";
            textColor = "text-red-600 font-medium";
          } else if (entry.status === "in_progress") {
            Icon = Loader2;
            iconColor = "text-blue-500";
            textColor = "text-blue-600 font-medium";
          }
        }

        return (
          <div key={stageKey} className="flex items-start space-x-3">
            <div className={`mt-0.5 relative ${isActive ? "animate-pulse" : ""}`}>
              {/* Vertical connecting line for all but the last item */}
              {idx < STAGE_ORDER.length - 1 && (
                <div 
                  className={`absolute left-[9px] top-5 w-[2px] h-4 ${
                    entry?.status === "complete" ? "bg-emerald-500" : "bg-gray-100"
                  }`} 
                />
              )}
              <Icon className={`w-5 h-5 ${iconColor} ${entry?.status === "in_progress" ? "animate-spin" : ""}`} />
            </div>
            <span className={`text-sm ${textColor}`}>
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Fallback labels for pending stages before the backend sends them
function getPendingLabel(stageKey: string): string {
  const labels: Record<string, string> = {
    parsing_question: "Classifying your question...",
    resolving_entities: "Identifying relevant metrics and dimensions...",
    planning_query: "Building the query plan...",
    generating_sql: "Compiling SQL...",
    executing_query: "Running the query...",
    generating_insights: "Generating natural language insights...",
  };
  return labels[stageKey] || "Waiting...";
}
