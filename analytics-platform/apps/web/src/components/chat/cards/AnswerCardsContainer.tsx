import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { LayoutGrid, AlignLeft, FastForward } from 'lucide-react';
import { parseMarkdownToCards } from './cardParser';
import { useCardRevealQueue } from './useCardRevealQueue';
import { SummaryCard } from './SummaryCard';
import { PointCard } from './PointCard';
import { ListCard } from './ListCard';
import { ConclusionCard } from './ConclusionCard';
import { TableCard } from './TableCard';
import { MarkdownRenderer } from '../MarkdownRenderer';
import type { CardModel } from './types';

interface AnswerCardsContainerProps {
  content: string;
  isStreaming?: boolean;
  stopped?: boolean;
  isCodeIntel?: boolean;
  onAllCardsComplete?: () => void;
}

export const AnswerCardsContainer: React.FC<AnswerCardsContainerProps> = ({
  content,
  isStreaming,
  stopped,
  isCodeIntel,
  onAllCardsComplete,
}) => {
  // Local toggle between Cards view and Classic Markdown view
  const [isCardsMode, setIsCardsMode] = useState<boolean>(() => {
    try {
      // Default enabled if browser supports it, user can toggle anytime
      return localStorage.getItem('pref_cards_view') !== 'false';
    } catch {
      return true;
    }
  });

  // 1. Parse raw markdown into structured sections
  const parsed = useMemo(() => {
    return parseMarkdownToCards(content, { isCodeIntel });
  }, [content, isCodeIntel]);

  // Flatten all cards into a single sequential queue for progressive reveal
  const allCards = useMemo(() => {
    const list: CardModel[] = [];
    parsed.sections.forEach(s => {
      s.cards.forEach(c => list.push(c));
    });
    return list;
  }, [parsed.sections]);

  // 2. Sequential Reveal Hook
  const { activeCardIndex, revealedChars, isAllComplete, skipAnimation } = useCardRevealQueue({
    cards: allCards,
    isStreaming,
    stopped,
    onAllCardsComplete,
  });

  // If answer does not qualify for cards, or user selected plain markdown view:
  if (!parsed.canRenderCards || !isCardsMode) {
    return (
      <div style={{ position: 'relative' }}>
        {parsed.canRenderCards && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.4rem' }}>
            <button
              type="button"
              onClick={() => {
                setIsCardsMode(true);
                try { localStorage.setItem('pref_cards_view', 'true'); } catch {}
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.74rem',
                color: 'var(--text-muted)',
                background: 'transparent',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm, 6px)',
                padding: '2px 8px',
                cursor: 'pointer',
                opacity: 0.8,
              }}
              title="Switch to Cards view"
            >
              <LayoutGrid size={12} /> Cards view
            </button>
          </div>
        )}
        <MarkdownRenderer content={content} isStreaming={isStreaming} />
      </div>
    );
  }

  // Helper to render individual card component
  const renderCard = (card: CardModel, globalIdx: number) => {
    // If cards are still typing and this card has not yet mounted:
    if (!isAllComplete && globalIdx > activeCardIndex) {
      return null;
    }

    const isCardActive = !isAllComplete && globalIdx === activeCardIndex;
    const isCardFinished = isAllComplete || globalIdx < activeCardIndex;
    const currentChars = isCardActive ? revealedChars : undefined;

    switch (card.kind) {
      case 'summary':
        return <SummaryCard key={card.id} card={card} visibleChars={currentChars} isComplete={isCardFinished} />;
      case 'conclusion':
        return <ConclusionCard key={card.id} card={card} visibleChars={currentChars} isComplete={isCardFinished} />;
      case 'ordered_list':
      case 'bullet_list':
        return <ListCard key={card.id} card={card} visibleChars={currentChars} isComplete={isCardFinished} />;
      case 'table':
        return <TableCard key={card.id} card={card} visibleChars={currentChars} isComplete={isCardFinished} />;
      default:
        return <PointCard key={card.id} card={card} visibleChars={currentChars} isComplete={isCardFinished} />;
    }
  };

  let globalCardCounter = 0;

  return (
    <div style={{ width: '100%', position: 'relative', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Controls: Switch to Markdown & Skip Animation */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.5rem', marginBottom: '-0.5rem' }}>
        {!isAllComplete && (
          <button
            type="button"
            onClick={skipAnimation}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.3rem',
              fontSize: '0.72rem',
              color: 'var(--primary)',
              background: 'var(--primary-light)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: 'var(--radius-sm, 6px)',
              padding: '2px 8px',
              cursor: 'pointer',
              fontWeight: 600,
            }}
            title="Skip typing animation"
          >
            <FastForward size={11} /> Skip
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setIsCardsMode(false);
            try { localStorage.setItem('pref_cards_view', 'false'); } catch {}
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: '0.74rem',
            color: 'var(--text-muted)',
            background: 'transparent',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-sm, 6px)',
            padding: '2px 8px',
            cursor: 'pointer',
            opacity: 0.8,
          }}
          title="Switch to plain markdown view"
        >
          <AlignLeft size={12} /> Markdown view
        </button>
      </div>

      {/* Screen Reader Live Region */}
      <div aria-live="polite" className="sr-only" style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
        {isAllComplete ? 'Analysis cards loaded completely' : `Loading card ${activeCardIndex + 1} of ${allCards.length}`}
      </div>

      {/* 1. Plain Lead-in Intro Paragraph (if any exists before first heading) */}
      {parsed.introText && (
        <div
          style={{
            fontSize: '0.94rem',
            lineHeight: 1.65,
            color: 'var(--text-main)',
            fontFamily: 'var(--font-results, inherit)',
            maxWidth: '680px',
            margin: '0 auto',
            width: '100%',
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p style={{ margin: 0 }}>{children}</p>,
              strong: ({ children }) => <strong style={{ fontWeight: 600, color: 'var(--text-main)' }}>{children}</strong>,
            }}
          >
            {parsed.introText}
          </ReactMarkdown>
        </div>
      )}

      {/* 2. Structured Sections & Two-Column Grid */}
      {parsed.sections.map((section, sIdx) => {
        return (
          <section
            key={sIdx}
            aria-label={section.sectionLabel || `Section ${sIdx + 1}`}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.65rem',
              width: '100%',
              maxWidth: '680px',
              margin: '0 auto',
            }}
          >
            {/* Section Category Label */}
            {section.sectionLabel && (
              <h3
                style={{
                  fontSize: '1rem',
                  fontWeight: 700,
                  color: 'var(--text-main)',
                  margin: '0.65rem 0 0.15rem 0',
                  letterSpacing: '-0.01em',
                  fontFamily: 'var(--font-results, inherit)',
                }}
              >
                {section.sectionLabel}
              </h3>
            )}

            {/* 2-Column Responsive Card Grid */}
            <div
              className="chat-cards-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                gap: '0.85rem',
                width: '100%',
                alignItems: 'stretch',
              }}
            >
              {section.cards.map(card => {
                const currentGlobalIdx = globalCardCounter++;
                return renderCard(card, currentGlobalIdx);
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
};
