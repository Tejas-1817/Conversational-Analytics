// @vitest-environment jsdom
import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { InstantFilterTable } from '../InstantFilterTable';

const sampleData = [
  { id: 1, region: 'North', sales: 100, rep: 'Alice' },
  { id: 2, region: 'South', sales: 200, rep: 'Bob' },
  { id: 3, region: 'East', sales: 150, rep: 'Charlie' },
  { id: 4, region: 'West', sales: 300, rep: 'Alice' },
  { id: 5, region: 'North', sales: 120, rep: 'David' },
];

describe('InstantFilterTable Component', () => {
  afterEach(() => {
    cleanup();
  });
  it('renders all rows and columns properly', () => {
    render(<InstantFilterTable data={sampleData} columns={['region', 'sales', 'rep']} />);

    expect(screen.getByText('region')).toBeDefined();
    expect(screen.getByText('sales')).toBeDefined();
    expect(screen.getByText('rep')).toBeDefined();
    expect(screen.getByText(/records/i)).toBeDefined();
  });

  it('filters rows using global search input', () => {
    render(<InstantFilterTable data={sampleData} columns={['region', 'sales', 'rep']} />);

    const searchInput = screen.getByPlaceholderText(/search loaded rows/i);
    fireEvent.change(searchInput, { target: { value: 'Alice' } });

    expect(screen.getAllByText('Alice').length).toBe(2);
    expect(screen.queryByText('Bob')).toBeNull();
  });

  it('shows truncation warning banner when truncated is true', () => {
    render(<InstantFilterTable data={sampleData} truncated={true} />);

    expect(screen.getByText(/Result capped at 10,000 rows/i)).toBeDefined();
  });

  it('resets filters when Reset filters button is clicked', () => {
    render(<InstantFilterTable data={sampleData} columns={['region', 'sales', 'rep']} />);

    const searchInput = screen.getByPlaceholderText(/search loaded rows/i);
    fireEvent.change(searchInput, { target: { value: 'Alice' } });
    expect(screen.queryByText('Bob')).toBeNull();

    const resetBtn = screen.getByRole('button', { name: /reset filters/i });
    fireEvent.click(resetBtn);

    expect(screen.getByText('Bob')).toBeDefined();
  });
});
