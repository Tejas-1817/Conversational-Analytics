// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import React from 'react';
import { Dashboards } from '../Dashboards';
import * as apiModule from '../../../services/api';
import * as authContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/api', () => ({
  fetchApi: vi.fn(),
}));

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
  useLocation: () => ({ pathname: '/dashboards', search: '', key: 'default' }),
  Link: ({ children, to, ...props }: any) => <a href={to} {...props}>{children}</a>,
}));

vi.mock('react-grid-layout', () => {
  const MockRGL = ({ children }: any) => <div data-testid="mock-rgl">{children}</div>;
  return {
    default: MockRGL,
    Responsive: MockRGL,
    ResponsiveGridLayout: MockRGL,
    useContainerWidth: () => ({ width: 1200, containerRef: { current: null }, mounted: true, measureWidth: () => {} }),
  };
});

// Mock echarts to avoid canvas rendering issues in jsdom
vi.mock('../../../components/visualizations/ChartRenderer', () => ({
  ChartRenderer: ({ type, data, title }: any) => (
    <div data-testid="mock-chart-renderer">
      <span>{title}</span>
      <span>{type}</span>
      <span>{data?.length || 0} rows</span>
    </div>
  ),
}));

describe('Dashboards Page', () => {
  const mockUser = {
    id: 'user-owner-1',
    email: 'owner@example.com',
    role: 'USER',
    tenant_id: 'tenant-1',
  };

  const sampleDashboards = [
    {
      id: 'dash-1',
      user_id: 'user-owner-1',
      tenant_id: 'tenant-1',
      name: 'Revenue & Growth',
      description: 'Core revenue performance metrics',
      visibility: 'published',
      widgets: [
        {
          id: 'widget-1',
          dashboard_id: 'dash-1',
          insight_id: 'insight-1',
          x: 0,
          y: 0,
          w: 6,
          h: 4,
          title_override: 'Quarterly MRR Trend',
          chart_type_override: 'bar',
          insight: {
            id: 'insight-1',
            name: 'Quarterly MRR',
            query: 'SELECT quarter, mrr FROM mrr_summary',
            chart_type: 'bar',
          },
        },
      ],
    },
    {
      id: 'dash-2',
      user_id: 'user-owner-1',
      tenant_id: 'tenant-1',
      name: 'Marketing Funnel',
      description: 'Lead generation and conversions',
      visibility: 'private',
      widgets: [],
    },
  ];

  const sampleAvailableInsights = [
    {
      id: 'insight-2',
      name: 'Active Subscribers by Plan',
      chart_type: 'pie',
      query: 'SELECT plan, count(*) FROM subscriptions GROUP BY plan',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (authContextModule.useAuth as any).mockReturnValue({
      user: mockUser,
      loading: false,
    });

    (apiModule.fetchApi as any).mockImplementation((path: string, options?: any) => {
      if (path === '/dashboards' && (!options || options.method === 'GET' || !options.method)) {
        return Promise.resolve(sampleDashboards);
      }
      if (path === '/dashboards/dash-1') {
        return Promise.resolve(sampleDashboards[0]);
      }
      if (path === '/dashboards/insights') {
        return Promise.resolve(sampleAvailableInsights);
      }
      if (path === '/dashboards/insights/insight-1/run') {
        return Promise.resolve({
          status: 'success',
          locked: false,
          data: [
            { quarter: 'Q1', mrr: 120000 },
            { quarter: 'Q2', mrr: 155000 },
          ],
          columns: ['quarter', 'mrr'],
          column_types: { quarter: 'varchar', mrr: 'numeric' },
          row_count: 2,
          execution_time_ms: 14.2,
        });
      }
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders dashboard header and widgets', async () => {
    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getAllByText('Revenue & Growth').length).toBeGreaterThanOrEqual(1);
    });

    // Check widget title rendered
    await waitFor(() => {
      expect(screen.getByText('Quarterly MRR Trend')).toBeDefined();
    });

    // Open More options dropdown on widget
    const moreOptionsBtn = screen.getByTitle('More options');
    fireEvent.click(moreOptionsBtn);

    // Check chart type options (Table, Bar, Line, Pie)
    expect(screen.getByText('Table')).toBeDefined();
    expect(screen.getByText('Bar Chart')).toBeDefined();
    expect(screen.getByText('Line Chart')).toBeDefined();
    expect(screen.getByText('Pie Chart')).toBeDefined();
  });

  it('renders locked state when insight run endpoint returns locked status', async () => {
    (apiModule.fetchApi as any).mockImplementation((path: string, options?: any) => {
      if (path === '/dashboards') {
        return Promise.resolve(sampleDashboards);
      }
      if (path === '/dashboards/dash-1') {
        return Promise.resolve(sampleDashboards[0]);
      }
      if (path === '/dashboards/insights') {
        return Promise.resolve([]);
      }
      if (path === '/dashboards/insights/insight-1/run') {
        return Promise.resolve({
          status: 'locked',
          locked: true,
          detail: 'You do not have permission to view table "mrr_summary".',
        });
      }
      return Promise.resolve({});
    });

    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getByText('Data Access Restricted')).toBeDefined();
      expect(
        screen.getByText(/You do not have permission to view table "mrr_summary"/i)
      ).toBeDefined();
    });
  });

  it('opens Add Insights slide-over drawer and displays available insights', async () => {
    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getAllByText('Revenue & Growth').length).toBeGreaterThanOrEqual(1);
    });

    const addInsightBtn = screen.getByRole('button', { name: /Add Insight/i });
    fireEvent.click(addInsightBtn);

    await waitFor(() => {
      expect(screen.getByText('Add Insights to Dashboard')).toBeDefined();
      expect(screen.getByText('Active Subscribers by Plan')).toBeDefined();
    });
  });

  it('displays delete confirmation modal when Delete Dashboard is triggered in settings', async () => {
    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getAllByText('Revenue & Growth').length).toBeGreaterThanOrEqual(1);
    });

    const settingsBtn = screen.getByTitle('Dashboard Settings');
    fireEvent.click(settingsBtn);

    await waitFor(() => {
      expect(screen.getByText('Dashboard Settings')).toBeDefined();
    });

    const deleteBtn = screen.getByRole('button', { name: /Delete Dashboard/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.getByText('Delete Dashboard?')).toBeDefined();
      expect(screen.getByText(/Are you sure you want to delete/i)).toBeDefined();
    });
  });

  it('allows switching dashboards via the dropdown selector', async () => {
    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getAllByText('Revenue & Growth').length).toBeGreaterThanOrEqual(1);
    });

    const trigger = screen.getByLabelText('Select Dashboard');
    expect(trigger).toBeDefined();

    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /Marketing Funnel/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('option', { name: /Marketing Funnel/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Marketing Funnel').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('opens New Dashboard modal and handles dashboard creation', async () => {
    (apiModule.fetchApi as any).mockImplementation((path: string, options?: any) => {
      if (path === '/dashboards' && options?.method === 'POST') {
        const body = JSON.parse(options.body);
        return Promise.resolve({
          id: 'dash-new',
          user_id: 'user-owner-1',
          tenant_id: 'tenant-1',
          name: body.name,
          description: body.description,
          visibility: body.visibility,
          widgets: [],
        });
      }
      if (path === '/dashboards') {
        return Promise.resolve(sampleDashboards);
      }
      if (path === '/dashboards/dash-1') {
        return Promise.resolve(sampleDashboards[0]);
      }
      if (path === '/dashboards/insights') {
        return Promise.resolve([]);
      }
      return Promise.resolve({});
    });

    render(<Dashboards />);

    await waitFor(() => {
      expect(screen.getAllByText('Revenue & Growth').length).toBeGreaterThanOrEqual(1);
    });

    const newDashBtn = screen.getByRole('button', { name: /New Dashboard/i });
    fireEvent.click(newDashBtn);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/e\.g\. Executive Performance Overview/i)).toBeDefined();
    });

    const nameInput = screen.getByPlaceholderText(/e\.g\. Executive Performance Overview/i);
    fireEvent.change(nameInput, { target: { value: 'Customer Churn Analysis' } });

    const submitBtn = screen.getByRole('button', { name: /Create Dashboard/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        '/dashboards',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });
});
