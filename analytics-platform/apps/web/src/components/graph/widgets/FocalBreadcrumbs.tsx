import React from 'react';
import { Target, X, Share2, Layers } from 'lucide-react';
import type { DomainGraphNode } from '../types';

interface FocalBreadcrumbsProps {
  focalNode: DomainGraphNode | null;
  focalHops: 1 | 2;
  onChangeHops: (hops: 1 | 2) => void;
  onExitFocalMode: () => void;
  visibleTableCount: number;
  totalTableCount: number;
}

export const FocalBreadcrumbs: React.FC<FocalBreadcrumbsProps> = ({
  focalNode,
  focalHops,
  onChangeHops,
  onExitFocalMode,
  visibleTableCount,
  totalTableCount,
}) => {
  if (!focalNode) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 25,
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '6px 14px',
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #C7D2FE',
        borderRadius: '30px',
        boxShadow: '0 4px 16px rgba(79, 70, 229, 0.15)',
        fontSize: '12px',
      }}
    >
      {/* Focal Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#4338CA', fontWeight: 700 }}>
        <Target size={15} style={{ color: '#4F46E5' }} />
        <span>Focal Mode:</span>
        <span
          style={{
            background: '#4F46E5',
            color: '#FFFFFF',
            padding: '2px 8px',
            borderRadius: '12px',
            fontSize: '11.5px',
          }}
        >
          {focalNode.table_name}
        </span>
      </div>

      <div style={{ width: '1px', height: '14px', background: '#E2E8F0' }} />

      {/* Scope Details */}
      <span style={{ color: 'var(--text-muted)', fontSize: '11.5px' }}>
        Showing <b>{visibleTableCount}</b> of {totalTableCount} tables
      </span>

      {/* Hops Toggle */}
      <div
        style={{
          display: 'flex',
          background: '#F1F5F9',
          borderRadius: '16px',
          padding: '2px',
        }}
      >
        <button
          onClick={() => onChangeHops(1)}
          style={{
            padding: '2px 8px',
            fontSize: '10.5px',
            fontWeight: 700,
            border: 'none',
            borderRadius: '12px',
            cursor: 'pointer',
            background: focalHops === 1 ? '#4F46E5' : 'transparent',
            color: focalHops === 1 ? '#FFFFFF' : '#64748B',
            transition: 'all 0.15s ease',
          }}
        >
          1-Hop (Direct)
        </button>
        <button
          onClick={() => onChangeHops(2)}
          style={{
            padding: '2px 8px',
            fontSize: '10.5px',
            fontWeight: 700,
            border: 'none',
            borderRadius: '12px',
            cursor: 'pointer',
            background: focalHops === 2 ? '#4F46E5' : 'transparent',
            color: focalHops === 2 ? '#FFFFFF' : '#64748B',
            transition: 'all 0.15s ease',
          }}
        >
          2-Hops
        </button>
      </div>

      <div style={{ width: '1px', height: '14px', background: '#E2E8F0' }} />

      {/* Exit Button */}
      <button
        onClick={onExitFocalMode}
        title="Exit Focal Mode and show all tables"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '3px 8px',
          fontSize: '11px',
          fontWeight: 600,
          background: '#FEE2E2',
          color: '#DC2626',
          border: '1px solid #FCA5A5',
          borderRadius: '12px',
          cursor: 'pointer',
        }}
      >
        <X size={12} />
        <span>Reset to Full Schema</span>
      </button>
    </div>
  );
};
