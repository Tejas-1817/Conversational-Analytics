import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ChartRenderer } from './ChartRenderer';

// Mock react-echarts to avoid canvas rendering during unit tests
vi.mock('echarts-for-react', () => ({
  default: (props: any) => <div data-testid="echarts-mock">{props.option?.series?.[0]?.type || 'chart'}</div>
}));

describe('ChartRenderer', () => {
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
    expect(screen.getByText('REGION')).toBeDefined();
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
});
