import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';
import { ChatInterface } from '../ChatInterface';
import * as apiModule from '../../../services/api';

vi.mock('../../../services/api', () => ({
  fetchApi: vi.fn(),
  APIError: class extends Error {},
}));

vi.mock('../../../components/visualizations/ChartRenderer', () => ({
  ChartRenderer: () => <div data-testid="chart-renderer" />,
}));

vi.mock('../../../components/chat/MarkdownRenderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown-content">{content}</div>,
}));

vi.mock('../../../components/chat/ThoughtSteps', () => ({
  ThoughtSteps: ({ activeStage }: { activeStage?: string }) => (
    <div data-testid="thought-steps">{activeStage || 'Thinking'}</div>
  ),
}));

vi.mock('../../../components/chat/FollowUpSuggestions', () => ({
  FollowUpSuggestions: () => <div data-testid="follow-ups" />,
}));

describe('ChatInterface - Stop Generating feature', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
    localStorage.setItem('active_chat_source_id', 'src-1');

    (apiModule.fetchApi as any).mockImplementation((endpoint: string) => {
      if (endpoint === '/domains') return Promise.resolve([]);
      if (endpoint === '/sources') return Promise.resolve([{ id: 'src-1', name: 'Main DB', type: 'postgres' }]);
      if (endpoint === '/code-repos') return Promise.resolve([]);
      if (endpoint === '/engine/conversations') return Promise.resolve([]);
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renders Stop button and hides Send button while a request is pending', async () => {
    // Unresolved fetch to keep request pending
    let capturedSignal: any = null;
    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      capturedSignal = options.signal;
      return new Promise(() => {}); // Never resolves
    });

    render(<ChatInterface />);

    // Wait for sources to load
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'How many customers?' } });

    // Send button exists
    const sendButton = screen.getByRole('button', { name: '' });
    expect(sendButton).toBeDefined();

    // Submit question
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    // Stop button is now visible
    await waitFor(() => {
      const stopButton = screen.getByRole('button', { name: /stop generating/i });
      expect(stopButton).toBeDefined();
    });

    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);
  });

  it('clicking Stop calls abort on controller, shows no error bubble, and re-enables textarea', async () => {
    let capturedSignal: any = null;
    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      capturedSignal = options.signal;
      return new Promise((_, reject) => {
        options.signal?.addEventListener('abort', () => {
          const err = new Error('The user aborted a request.');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Revenue breakdown' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop generating/i })).toBeDefined();
    });

    const stopButton = screen.getByRole('button', { name: /stop generating/i });
    fireEvent.click(stopButton);

    // Controller was aborted
    expect(capturedSignal?.aborted).toBe(true);

    // No error bubble should be displayed
    await waitFor(() => {
      expect(screen.queryByText(/failed to process query/i)).toBeNull();
      // Textarea re-enabled
      expect(textarea.disabled).toBe(false);
    });
  });

  it('pressing Esc while loading triggers stop; pressing Esc when idle does nothing', async () => {
    let aborted = false;
    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      options.signal?.addEventListener('abort', () => {
        aborted = true;
      });
      return new Promise(() => {});
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    // Pressing Esc while idle
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(aborted).toBe(false);

    // Start loading
    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Count users' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop generating/i })).toBeDefined();
    });

    // Pressing Esc while loading
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

    await waitFor(() => {
      expect(aborted).toBe(true);
    });
  });

  it('removes empty assistant placeholder if stopped before any token arrived', async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      return new Promise((_, reject) => {
        options.signal?.addEventListener('abort', () => {
          const err = new Error('The user aborted a request.');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Show trends' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop generating/i })).toBeDefined();
    });

    // Click stop before any tokens arrived
    fireEvent.click(screen.getByRole('button', { name: /stop generating/i }));

    await waitFor(() => {
      // User message remains
      expect(screen.getByText('Show trends')).toBeDefined();
      // But no assistant content or stopped label exists because it was empty
      expect(screen.queryByText('Stopped')).toBeNull();
    });
  });

  it('handles early meta SSE event to set conversation ID', async () => {
    const ssePayload = 'data: {"type": "meta", "conversation_id": "conv-test-999"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(ssePayload));
        controller.close();
      }
    });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Show orders' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(localStorage.getItem('active_conversation_id')).toBe('conv-test-999');
    });
  });

  it('keeps partial text and marks message as stopped when aborted mid-stream', async () => {
    let streamController: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream({
      start(c) {
        streamController = c;
      }
    });

    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      options.signal?.addEventListener('abort', () => {
        try {
          streamController?.error(new DOMException('Aborted', 'AbortError'));
        } catch (_) {}
      });
      return Promise.resolve({
        ok: true,
        body: stream,
      });
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Analyze inventory' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    // Feed some tokens
    act(() => {
      streamController.enqueue(new TextEncoder().encode('data: {"type": "token", "delta": "Inventory is healthy"}\n\n'));
    });

    // Wait for text to be typed by pump
    await waitFor(() => {
      expect(screen.getByText(/Inventory is healthy/i)).toBeDefined();
    }, { timeout: 3000 });

    // Click stop button
    const stopButton = screen.getByRole('button', { name: /stop generating/i });
    fireEvent.click(stopButton);

    // Partial text remains and Stopped label appears
    await waitFor(() => {
      expect(screen.getByText(/Inventory is healthy/i)).toBeDefined();
      expect(screen.getByText('Stopped')).toBeDefined();
    });
  });

  it('keeps SQL and data fields when stop occurs after finalData has arrived', async () => {
    let streamController: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream({
      start(c) {
        streamController = c;
      }
    });

    globalThis.fetch = vi.fn().mockImplementation((_url: string, options: any) => {
      options.signal?.addEventListener('abort', () => {
        try {
          streamController?.error(new DOMException('Aborted', 'AbortError'));
        } catch (_) {}
      });
      return Promise.resolve({
        ok: true,
        body: stream,
      });
    });

    render(<ChatInterface />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask about your data...')).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText('Ask about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Show revenue' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    // Feed token + finalData complete payload
    act(() => {
      streamController.enqueue(new TextEncoder().encode('data: {"type": "token", "delta": "Revenue summary"}\n\n'));
      streamController.enqueue(new TextEncoder().encode('data: {"type": "complete", "result": {"sql": "SELECT sum(amount) FROM sales", "rows": [{"total": 95000}], "columns": ["total"], "answer": "Revenue summary"}}\n\n'));
    });

    await waitFor(() => {
      expect(screen.getByText(/Revenue summary/i)).toBeDefined();
    }, { timeout: 3000 });

    // Click stop while pump was finishing
    const stopButton = screen.queryByRole('button', { name: /stop generating/i });
    if (stopButton) {
      fireEvent.click(stopButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/Revenue summary/i)).toBeDefined();
      // SQL accordion header is rendered
      expect(screen.getByText(/Generated SQL Query/i)).toBeDefined();
      expect(screen.getByText('Stopped')).toBeDefined();
    });
  });
});
