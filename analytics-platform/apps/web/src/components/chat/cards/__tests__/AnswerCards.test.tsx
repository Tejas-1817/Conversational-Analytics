import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { AnswerCardsContainer } from '../AnswerCardsContainer';

describe('AnswerCardsContainer & Progressive Reveal', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const sampleMarkdown = `
## Executive Summary
Overall assessment of the portfolio performance shows strong retention.

## Key Risk Areas
Data limitation identified in payment transactions due to delayed webhooks.

## Conclusion
Recommend scheduling automated daily health score syncs.
`;

  it('renders all cards immediately when isStreaming is false (e.g. reloaded history)', () => {
    render(<AnswerCardsContainer content={sampleMarkdown} isStreaming={false} />);

    expect(screen.getByText(/Executive Summary/i)).toBeDefined();
    expect(screen.getByText(/Key Risk Areas/i)).toBeDefined();
    expect(screen.getByText(/Conclusion/i)).toBeDefined();
    expect(screen.getByText(/Overall assessment of the portfolio/i)).toBeDefined();
  });

  it('renders plain markdown when answer is not eligible for cards', () => {
    const plainText = 'The query returned 42 matching customer records.';
    render(<AnswerCardsContainer content={plainText} isStreaming={false} />);

    expect(screen.getByText(/The query returned 42 matching customer records/i)).toBeDefined();
    expect(screen.queryByTitle('Switch to Cards view')).toBeNull();
  });

  it('allows user to toggle to Markdown view and back to Cards view', () => {
    render(<AnswerCardsContainer content={sampleMarkdown} isStreaming={false} />);

    // Toggle to Markdown
    const markdownBtn = screen.getByRole('button', { name: /markdown view/i });
    fireEvent.click(markdownBtn);

    // Cards view button is now available to switch back
    const cardsBtn = screen.getByRole('button', { name: /cards view/i });
    expect(cardsBtn).toBeDefined();

    // Click back to Cards view
    fireEvent.click(cardsBtn);
    expect(screen.getByText(/Executive Summary/i)).toBeDefined();
  });

  it('reveals cards sequentially during streaming with fake timers', () => {
    vi.useFakeTimers();

    render(<AnswerCardsContainer content={sampleMarkdown} isStreaming={true} />);

    // Card 0 (Executive Summary) mounts first
    expect(screen.getByText(/Executive Summary/i)).toBeDefined();

    // Advance timer partway for Card 0
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Advance timer until Card 0 completes and Card 1 mounts
    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(screen.getByText(/Key Risk Areas/i)).toBeDefined();

    // Advance to end of all cards
    act(() => {
      vi.advanceTimersByTime(2500);
    });

    expect(screen.getByText(/Conclusion/i)).toBeDefined();
  });

  it('freezes active card and halts reveal when stopped is true', () => {
    vi.useFakeTimers();

    const { rerender } = render(
      <AnswerCardsContainer content={sampleMarkdown} isStreaming={true} stopped={false} />
    );

    // Let Card 0 type some characters
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Stop generation
    rerender(
      <AnswerCardsContainer content={sampleMarkdown} isStreaming={false} stopped={true} />
    );

    // No timer runs further
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText(/Executive Summary/i)).toBeDefined();
  });

  it('renders instantly without animation if total cards exceed threshold', () => {
    const longSections = Array.from({ length: 12 }, (_, i) => `## Section ${i + 1}\nDescription of section ${i + 1} with details.`).join('\n\n');

    render(<AnswerCardsContainer content={longSections} isStreaming={true} />);

    // All sections render immediately without typing queue
    expect(screen.getAllByText(/Section 12/i).length).toBeGreaterThanOrEqual(1);
  });
});
