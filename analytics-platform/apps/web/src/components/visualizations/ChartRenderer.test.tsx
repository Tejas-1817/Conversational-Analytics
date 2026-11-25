// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
import { ChartRenderer } from './ChartRenderer';

// Mock react-echarts to avoid canvas rendering during unit tests
vi.mock('echarts-for-react', () => ({
  default: (props: any) => <div data-testid="echarts-mock">{props.option?.series?.[0]?.type || 'chart'}</div>
}));

describe('ChartRenderer', () => {
  afterEach(() => {
    cleanup();
  });
  it('renders a KPI card correctly', () => {
    const data = {
      columns: ['Revenue'],
      rows: [{ 'Revenue': 150000 }]
    };
    render(<ChartRenderer data={data} chartType="kpi_card" />);
    expect(screen.getByText('Revenue')).toBeDefined();
    expect(screen.getByText('150,000')).toBeDefined();
  });

  it('renders a Table correctly and allows sorting', () => {
    const data = {
      columns: ['Region', 'Revenue'],
      rows: [
        { 'Region': 'North America', 'Revenue': 50000 },
        { 'Region': 'Europe', 'Revenue': 45000 }
      ]
    };
    render(<ChartRenderer data={data} chartType="table" />);
    expect(screen.getByText(/Region/i)).toBeDefined();
    expect(screen.getByText('North America')).toBeDefined();
    expect(screen.getByText('Europe')).toBeDefined();
  });

  it('renders interactive chart with toolbar and switches chart types', () => {
    const data = {
      columns: ['Category', 'Sales'],
      rows: [
        { 'Category': 'Electronics', 'Sales': 12000 },
        { 'Category': 'Clothing', 'Sales': 8000 }
      ]
    };
    render(<ChartRenderer data={data} chartType="bar_chart" title="Category Sales" />);
    expect(screen.getByText('Category Sales')).toBeDefined();
    expect(screen.getByTestId('echarts-mock')).toBeDefined();
  });

  it('opens 3-dots dropdown menu with all 4 options', () => {
    const onSaveInsight = vi.fn();
    const onDownloadCSV = vi.fn();
    const data = {
      columns: ['Category', 'Sales'],
      rows: [
        { 'Category': 'Electronics', 'Sales': 12000 },
        { 'Category': 'Clothing', 'Sales': 8000 }
      ]
    };
    render(
      <ChartRenderer
        data={data}
        chartType="bar_chart"
        title="Category Sales"
        onSaveInsight={onSaveInsight}
        onDownloadCSV={onDownloadCSV}
      />
    );

    const moreBtn = screen.getByTitle('More options');
    expect(moreBtn).toBeDefined();
    fireEvent.click(moreBtn);

    expect(screen.getByText('Save insight to dashboard')).toBeDefined();
    expect(screen.getByText('Download CSV')).toBeDefined();
    expect(screen.getByText('Download PNG image')).toBeDefined();
    expect(screen.getByText('Export CSV')).toBeDefined();

    fireEvent.click(screen.getByText('Save insight to dashboard'));
    expect(onSaveInsight).toHaveBeenCalledTimes(1);
  });

  it('dynamically computes Pattern A title when title is generic or missing', () => {
    const data = {
      columns: ['customer_name', 'negative_news_count', 'revenue_at_risk'],
      rows: [
        { customer_name: 'Acme', negative_news_count: 3, revenue_at_risk: 150000 },
        { customer_name: 'Beta', negative_news_count: 1, revenue_at_risk: 80000 }
      ]
    };

    // When generic title "Multi-Domain Pattern Analysis" is provided
    render(
      <ChartRenderer
        data={data}
        chartType="bar_chart"
        title="Multi-Domain Pattern Analysis"
      />
    );
    expect(screen.getByText('Negative News Count & Revenue At Risk by Customer')).toBeDefined();
    cleanup();

    // When no title is provided at all
    render(
      <ChartRenderer
        data={data}
        chartType="bar_chart"
      />
    );
    expect(screen.getByText('Negative News Count & Revenue At Risk by Customer')).toBeDefined();
  });
});
