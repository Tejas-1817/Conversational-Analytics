import React from 'react';
import type { CardTone, CardKind } from './types';
import { TONE_TOKEN_MAP } from './cardToneConfig';
import {
  Lightbulb,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Info,
  ListOrdered,
  ListChecks,
  Table as TableIcon,
  TrendingUp,
} from 'lucide-react';

interface IconBadgeProps {
  kind: CardKind;
  tone: CardTone;
  customIcon?: React.ReactNode;
}

export const IconBadge: React.FC<IconBadgeProps> = ({ kind, tone, customIcon }) => {
  const tokens = TONE_TOKEN_MAP[tone] || TONE_TOKEN_MAP.primary;

  const renderIcon = () => {
    if (customIcon) return customIcon;
    switch (kind) {
      case 'summary':
        return <Lightbulb size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'warning':
        return <AlertTriangle size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'conclusion':
        return <CheckCircle2 size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'info':
        return <Info size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'ordered_list':
        return <ListOrdered size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'bullet_list':
        return <ListChecks size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      case 'table':
        return <TableIcon size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
      default:
        return <Lightbulb size={15} style={{ color: tokens.badgeColor }} aria-hidden="true" />;
    }
  };

  return (
    <div
      style={{
        width: '28px',
        height: '28px',
        borderRadius: 'var(--radius-sm, 6px)',
        backgroundColor: tokens.badgeBg,
        border: `1px solid ${tokens.badgeBorder}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
      aria-hidden="true"
    >
      {renderIcon()}
    </div>
  );
};
