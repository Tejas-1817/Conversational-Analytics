import { useState, useEffect, useRef, useCallback } from 'react';
import type { CardModel } from './types';

export const MAX_ANIMATED_CARDS = 8;
export const MAX_ANIMATED_CHARS = 2500;
export const TARGET_ANIMATION_MS = 3500;

interface UseCardRevealQueueProps {
  cards: CardModel[];
  isStreaming?: boolean;
  stopped?: boolean;
  onAllCardsComplete?: () => void;
}

export function useCardRevealQueue({
  cards,
  isStreaming,
  stopped,
  onAllCardsComplete,
}: UseCardRevealQueueProps) {
  const [activeCardIndex, setActiveCardIndex] = useState(0);
  const [revealedChars, setRevealedChars] = useState(0);
  const [isAllComplete, setIsAllComplete] = useState(!isStreaming || Boolean(stopped));
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Compute total characters across all cards
  const totalChars = cards.reduce((sum, c) => sum + (c.fullMarkdown?.length || 100), 0);
  const isTooLongToAnimate = cards.length > MAX_ANIMATED_CARDS || totalChars > MAX_ANIMATED_CHARS;

  // Immediate completion handler
  const completeAll = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setActiveCardIndex(cards.length);
    setIsAllComplete(true);
    onAllCardsComplete?.();
  }, [cards.length, onAllCardsComplete]);

  // Handle Stop generation partway
  useEffect(() => {
    if (stopped) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setIsAllComplete(true);
    }
  }, [stopped]);

  // Main Sequential Reveal Engine
  useEffect(() => {
    // 1. If not streaming, or already stopped, or 0 cards, or prefers-reduced-motion, or too long -> complete immediately
    const prefersReducedMotion = typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!isStreaming || stopped || cards.length === 0 || prefersReducedMotion || isTooLongToAnimate) {
      completeAll();
      return;
    }

    // 2. Sequential typing loop
    let currentIdx = 0;
    let currentCharCount = 0;
    const currentCard = cards[0];
    const cardLength = currentCard ? (currentCard.fullMarkdown?.length || 150) : 150;

    // Calculate adaptive step size: finish all cards within ~3.5 seconds
    const framesTotal = Math.round(TARGET_ANIMATION_MS / 16);
    const stepSize = Math.max(3, Math.ceil(totalChars / framesTotal));

    timerRef.current = setInterval(() => {
      const activeCard = cards[currentIdx];
      if (!activeCard) {
        completeAll();
        return;
      }

      const activeLen = activeCard.fullMarkdown?.length || 150;
      currentCharCount += stepSize;

      if (currentCharCount >= activeLen) {
        // Current card completed! Move to next card
        currentIdx++;
        currentCharCount = 0;
        setActiveCardIndex(currentIdx);
        setRevealedChars(0);

        if (currentIdx >= cards.length) {
          completeAll();
        }
      } else {
        setRevealedChars(currentCharCount);
      }
    }, 16);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isStreaming, stopped, cards, totalChars, isTooLongToAnimate, completeAll]);

  return {
    activeCardIndex,
    revealedChars,
    isAllComplete,
    skipAnimation: completeAll,
  };
}
