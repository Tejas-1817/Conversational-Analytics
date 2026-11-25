// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import React from 'react';
import { SaveInsightModal } from '../SaveInsightModal';
import * as apiModule from '../../../services/api';

vi.mock('../../../services/api', () => ({
  fetchApi: vi.fn(),
}));

describe('SaveInsightModal', () => {
  const mockOnClose = vi.fn();
  const mockOnSaved = vi.fn();

  const sampleMessage = {
    id: 'msg-123',
    question: 'What is monthly recurring revenue?',
    query: 'SELECT month, sum(mrr) as revenue FROM mrr_table GROUP BY month',
    columns: ['month', 'revenue'],
    result_data: [{ month: '2026-01', revenue: 10000 }],
    recommended_visualization: {
      title: 'Monthly Recurring Revenue',
      chart_type: 'bar',
      columns: ['month', 'revenue'],
      column_types: { month: 'varchar', revenue: 'numeric' },
      data: [{ month: '2026-01', revenue: 10000 }],
    },
  };

  const sampleDashboards = [
    { id: 'dash-1', name: 'Executive Overview', visibility: 'published' },
    { id: 'dash-2', name: 'Sales Pipeline', visibility: 'private' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (apiModule.fetchApi as any).mockImplementation((path: string, options?: any) => {
      if (path === '/dashboards' && (!options || options.method === 'GET' || !options.method)) {
        return Promise.resolve(sampleDashboards);
      }
      if (path === '/dashboards/insights' && options?.method === 'POST') {
        const body = JSON.parse(options.body);
        return Promise.resolve({
          id: 'insight-999',
          name: body.name,
          query: body.query,
          chart_type: body.chart_type,
          chart_config: body.chart_config,
        });
      }
      if (path === '/dashboards/dash-1/widgets' && options?.method === 'POST') {
        return Promise.resolve({ id: 'widget-101' });
      }
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('does not render when isOpen is false', () => {
    render(
      <SaveInsightModal
        isOpen={false}
        onClose={mockOnClose}
        message={sampleMessage}
        onSaved={mockOnSaved}
      />
    );
    expect(screen.queryByText(/Save Insight to Dashboard/i)).toBeNull();
  });

  it('renders with prefilled title and loads available dashboards', async () => {
    render(
      <SaveInsightModal
        isOpen={true}
        onClose={mockOnClose}
        message={sampleMessage}
        sourceId="source-1"
        domainId="domain-1"
        conversationId="conv-1"
        onSaved={mockOnSaved}
      />
    );

    expect(screen.getByText('Save Insight')).toBeDefined();
    const nameInput = screen.getByLabelText(/Insight Name/i) as HTMLInputElement;
    expect(nameInput.value).toBe('Monthly Recurring Revenue');

    await waitFor(() => {
      expect(screen.getByText('Executive Overview')).toBeDefined();
      expect(screen.getByText('Sales Pipeline')).toBeDefined();
    });
  });

  it('allows switching to inline new dashboard creation', async () => {
    render(
      <SaveInsightModal
        isOpen={true}
        onClose={mockOnClose}
        message={sampleMessage}
        onSaved={mockOnSaved}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Executive Overview')).toBeDefined();
    });

    const createNewBtn = screen.getByRole('button', { name: /Create new dashboard/i });
    fireEvent.click(createNewBtn);

    expect(screen.getByPlaceholderText(/e.g. Executive Performance/i)).toBeDefined();
  });

  it('saves insight and strips raw data rows from payload', async () => {
    render(
      <SaveInsightModal
        isOpen={true}
        onClose={mockOnClose}
        message={sampleMessage}
        sourceId="source-1"
        domainId="domain-1"
        conversationId="conv-1"
        onSaved={mockOnSaved}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Executive Overview')).toBeDefined();
    });

    const saveBtn = screen.getByRole('button', { name: /Save to Dashboard/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        '/dashboards/insights',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    // Check that POST payload does NOT contain raw data rows
    const insightPostCall = (apiModule.fetchApi as any).mock.calls.find(
      (call: any[]) => call[0] === '/dashboards/insights'
    );
    expect(insightPostCall).toBeDefined();
    const parsedBody = JSON.parse(insightPostCall[1].body);
    expect(parsedBody.chart_config.data).toBeUndefined();
    expect(parsedBody.chart_config.columns).toEqual(['month', 'revenue']);

    await waitFor(() => {
      expect(mockOnSaved).toHaveBeenCalled();
    });
  });

  it('calls onClose when Cancel or Close button is clicked', () => {
    render(
      <SaveInsightModal
        isOpen={true}
        onClose={mockOnClose}
        message={sampleMessage}
        onSaved={mockOnSaved}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });
});
