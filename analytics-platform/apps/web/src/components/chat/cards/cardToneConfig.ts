import type { CardTone, CardKind } from './types';

export const CARD_TONE_CONFIG = {
  conclusion: ['conclusion', 'final takeaway', 'next steps', 'recommended next action', 'decision'],
  warning: ['risk', 'warning', 'caution', 'overdue', 'data limitation', 'limitations', 'missing data', 'sla breach', 'breach'],
  summary: ['summary', 'executive summary', 'overall assessment', 'overview'],
  info: ['note', 'notice', 'implementation notice', 'background', 'prerequisite'],
} as const;

export const CARD_TONE_PRECEDENCE: CardKind[] = [
  'conclusion',
  'warning',
  'summary',
  'info',
  'ordered_list',
  'bullet_list',
  'point',
];

/**
 * Resolves the card kind and visual tone based strictly on heading text (case-insensitive).
 */
export function resolveHeadingTone(headingText: string): { kind: CardKind; tone: CardTone } {
  const normalized = (headingText || '').toLowerCase().trim();

  // 1. Conclusion
  if (CARD_TONE_CONFIG.conclusion.some(k => normalized.includes(k))) {
    return { kind: 'conclusion', tone: 'success' };
  }

  // 2. Warning
  if (CARD_TONE_CONFIG.warning.some(k => normalized.includes(k))) {
    return { kind: 'warning', tone: 'warning' };
  }

  // 3. Summary
  if (CARD_TONE_CONFIG.summary.some(k => normalized.includes(k))) {
    return { kind: 'summary', tone: 'primary' };
  }

  // 4. Info
  if (CARD_TONE_CONFIG.info.some(k => normalized.includes(k))) {
    return { kind: 'info', tone: 'info' };
  }

  // Default: standard analytical point
  return { kind: 'point', tone: 'primary' };
}

export interface ToneTokens {
  badgeBg: string;
  badgeColor: string;
  badgeBorder: string;
  cardBorder: string;
  textColor: string;
  textAccent: string;
}

export const TONE_TOKEN_MAP: Record<CardTone, ToneTokens> = {
  primary: {
    badgeBg: 'var(--primary-light)',
    badgeColor: 'var(--primary)',
    badgeBorder: 'rgba(59, 130, 246, 0.2)',
    cardBorder: 'var(--border-color)',
    textColor: 'var(--text-main)',
    textAccent: 'var(--primary)',
  },
  warning: {
    badgeBg: 'var(--warning-light)',
    badgeColor: 'var(--warning)',
    badgeBorder: 'rgba(217, 119, 6, 0.25)',
    cardBorder: 'rgba(217, 119, 6, 0.35)',
    textColor: 'var(--text-main)',
    textAccent: 'var(--warning-text)',
  },
  success: {
    badgeBg: 'var(--success-light)',
    badgeColor: 'var(--success)',
    badgeBorder: 'rgba(22, 163, 74, 0.25)',
    cardBorder: 'rgba(22, 163, 74, 0.35)',
    textColor: 'var(--text-main)',
    textAccent: 'var(--success-text)',
  },
  info: {
    badgeBg: 'var(--info-light)',
    badgeColor: 'var(--info)',
    badgeBorder: 'rgba(14, 165, 233, 0.2)',
    cardBorder: 'var(--border-color)',
    textColor: 'var(--text-main)',
    textAccent: 'var(--info-text)',
  },
  neutral: {
    badgeBg: 'var(--bg-dark)',
    badgeColor: 'var(--text-muted)',
    badgeBorder: 'var(--border-color)',
    cardBorder: 'var(--border-color)',
    textColor: 'var(--text-main)',
    textAccent: 'var(--text-main)',
  },
};
