import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ChartRenderer } from './ChartRenderer';

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

  it('renders a Table correctly', () => {
    const data = {
      columns: ['Region', 'Revenue'],
      rows: [
        { 'Region': 'North America', 'Revenue': 50000 },
        { 'Region': 'Europe', 'Revenue': 45000 }
      ]
    };
    render(<ChartRenderer data={data} chartType="table" />);
    expect(screen.getByText('Region')).toBeDefined();
    expect(screen.getByText('North America')).toBeDefined();
  });
});
