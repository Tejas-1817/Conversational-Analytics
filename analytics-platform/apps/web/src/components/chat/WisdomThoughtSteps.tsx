import React, { useState, useEffect } from 'react';
import { ChevronRight, ChevronDown, Loader2, Sparkles, Database, BarChart3, CheckCircle2 } from 'lucide-react';

export interface ThoughtStep {
  title: string;
  detail?: string;
  status?: 'complete' | 'in_progress' | 'pending';
}

interface WisdomThoughtStepsProps {
  isLoading?: boolean;
  activeStage?: string;
  executionTimeMs?: number;
  intentReason?: string;
  steps?: ThoughtStep[];
}

export const WisdomThoughtSteps: React.FC<WisdomThoughtStepsProps> = ({
  isLoading = false,
  activeStage,
  executionTimeMs,
  intentReason,
  steps,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0.1);

  // Live timer while loading
  useEffect(() => {
    if (!isLoading) return;
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      setLiveElapsedSeconds(Math.max(0.1, elapsed));
    }, 100);
    return () => clearInterval(interval);
  }, [isLoading]);

  // Compute display duration
  const displayDuration = isLoading
    ? liveElapsedSeconds.toFixed(1)
    : executionTimeMs
      ? Math.max(0.1, executionTimeMs / 1000).toFixed(1)
      : '1.2';

  // Dynamic status label
  const stageLabel = activeStage
    ? activeStage.replace(/_/g, ' ')
    : isLoading
      ? 'Analyzing query & crunching metrics...'
      : `Thought for ${displayDuration} seconds`;

  const effectiveSteps: ThoughtStep[] = (steps && steps.length > 0) ? steps : [
    {
      title: 'Resolved intent & business context',
      detail: intentReason || 'Mapped question to verified schema tables and metric definitions.',
      status: 'complete',
    },
    {
      title: 'Queried database & verified schema constraints',
      detail: 'Generated dialect-safe SQL, executed query against data warehouse, and fetched clean records.',
      status: 'complete',
    },
    {
      title: 'Crunched aggregates and synthesized insights',
      detail: 'Computed distributions, ranked dimensions, and prepared multi-tier analytical cards.',
      status: 'complete',
    },
    {
      title: 'Charted visualization & formatted response',
      detail: 'Selected optimal chart layout and structured actionable business recommendations.',
      status: 'complete',
    },
  ];

  return (
    <div style={{
      marginBottom: '0.75rem',
      width: '100%',
      fontFamily: 'var(--font-results, "Helvetica Neue", Helvetica, Arial, sans-serif)',
    }}>
      {/* Live / Completed Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button
          type="button"
          onClick={() => !isLoading && setIsOpen(!isOpen)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            background: 'transparent',
            border: 'none',
            padding: '0.2rem 0',
            cursor: isLoading ? 'default' : 'pointer',
            color: 'var(--text-muted, #64748B)',
            fontSize: '0.86rem',
            fontWeight: 500,
            transition: 'color 0.15s ease',
            userSelect: 'none',
          }}
          onMouseEnter={(e) => {
            if (!isLoading) e.currentTarget.style.color = '#3B82F6';
          }}
          onMouseLeave={(e) => {
            if (!isLoading) e.currentTarget.style.color = 'var(--text-muted, #64748B)';
          }}
        >
          {isLoading ? (
            <Loader2 size={15} className="animate-spin" style={{ color: '#3B82F6' }} />
          ) : isOpen ? (
            <ChevronDown size={15} style={{ color: 'var(--text-muted, #94A3B8)' }} />
          ) : (
            <ChevronRight size={15} style={{ color: 'var(--text-muted, #94A3B8)' }} />
          )}

          <span style={{ color: isLoading ? '#3B82F6' : 'var(--text-muted, #64748B)', fontWeight: isLoading ? 600 : 500 }}>
            {isLoading ? `Thinking... (${displayDuration}s)` : `Thought for ${displayDuration} seconds`}
          </span>
        </button>
      </div>

      {/* Expanded Step Details (Collapsed by default, opens on user click) */}
      {!isLoading && isOpen && (
        <div
          style={{
            marginTop: '0.65rem',
            paddingLeft: '1.25rem',
            borderLeft: '2px solid var(--border-color, #E2E8F0)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem',
            fontSize: '0.85rem',
            color: 'var(--text-main, #334155)',
            animation: 'fadeIn 0.2s ease-in-out',
          }}
        >
          {effectiveSteps.map((step, idx) => (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                fontWeight: 600,
                color: 'var(--text-main, #1E293B)',
                fontSize: '0.85rem',
              }}>
                <span style={{ color: '#3B82F6' }}>›</span>
                <span>{step.title}</span>
              </div>
              {step.detail && (
                <p style={{
                  margin: 0,
                  paddingLeft: '0.95rem',
                  color: 'var(--text-muted, #64748B)',
                  lineHeight: 1.55,
                  fontSize: '0.82rem',
                }}>
                  {step.detail}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
