import { describe, it, expect } from 'vitest';
import {
  parseMarkdownToCards,
  evaluateCardEligibility,
  extractLabeledFields,
  formatMonospaceIdentifiers,
} from '../cardParser';
import { resolveHeadingTone } from '../cardToneConfig';

describe('cardParser & Tone Detection', () => {
  it('correctly resolves heading tone with precedence', () => {
    // Conclusion beats others
    expect(resolveHeadingTone('Conclusion and Summary')).toEqual({ kind: 'conclusion', tone: 'success' });
    // Warning beats summary
    expect(resolveHeadingTone('Summary of Critical Risks')).toEqual({ kind: 'warning', tone: 'warning' });
    // Summary
    expect(resolveHeadingTone('Executive Summary')).toEqual({ kind: 'summary', tone: 'primary' });
    expect(resolveHeadingTone('Overall Assessment')).toEqual({ kind: 'summary', tone: 'primary' });
    // Info
    expect(resolveHeadingTone('Implementation Notice')).toEqual({ kind: 'info', tone: 'info' });
    // Default Point
    expect(resolveHeadingTone('Customer Retention Dynamics')).toEqual({ kind: 'point', tone: 'primary' });
  });

  it('rejects short answers, raw tables, and plain code blocks from Cards Mode', () => {
    expect(evaluateCardEligibility('Total active accounts: 42.')).toBe(false);
    expect(evaluateCardEligibility('```sql\nSELECT * FROM users;\n```')).toBe(false);
    expect(evaluateCardEligibility('| id | name |\n|---|---|\n| 1 | Acme |')).toBe(false);
    expect(evaluateCardEligibility('Based on the verified database results, 3 rows were found.')).toBe(false);
    expect(evaluateCardEligibility('## Single Heading\nJust one section here.')).toBe(false);
  });

  it('exempts Code Intelligence answers even if they contain headings', () => {
    const md = '## Architecture\nOverview\n## Module Structure\nExports';
    expect(evaluateCardEligibility(md, { isCodeIntel: true })).toBe(false);
  });

  it('accepts multi-section reports with >= 2 headings', () => {
    const md = `
## Executive Summary
This is the overview of the customer data.

## Analytics Domains
### Customer Churn
Use: contracts, accounts
Possible analytics: Annual renewal rate

## Data Limitations
Missing timestamp records in audit log.

## Conclusion
Next steps are clearly outlined.
`;
    expect(evaluateCardEligibility(md)).toBe(true);
    const parsed = parseMarkdownToCards(md);
    expect(parsed.canRenderCards).toBe(true);
    expect(parsed.sections.length).toBeGreaterThanOrEqual(1);

    const allCards = parsed.sections.flatMap(s => s.cards);
    expect(allCards.length).toBeGreaterThanOrEqual(3);

    const summaryCard = allCards.find(c => c.kind === 'summary');
    expect(summaryCard).toBeDefined();
    expect(summaryCard?.tone).toBe('primary');

    const warningCard = allCards.find(c => c.kind === 'warning');
    expect(warningCard).toBeDefined();
    expect(warningCard?.tone).toBe('warning');

    const conclusionCard = allCards.find(c => c.kind === 'conclusion');
    expect(conclusionCard).toBeDefined();
    expect(conclusionCard?.tone).toBe('success');
  });

  it('accepts structured ordered action roadmap (Testable Activation Rule 3)', () => {
    const md = `
# Recommended Strategic Actions

1. **Review At-Risk Accounts**: Conduct immediate quarterly executive outreach for accounts with annual value exceeding $100k.
2. **Deploy Automated Alerts**: Integrate webhook monitors notifying account reps within 2 hours of payment delay.
3. **Audit Data Completeness**: Coordinate with data engineering to backfill missing subscription dates.
`;
    expect(evaluateCardEligibility(md)).toBe(true);
    const parsed = parseMarkdownToCards(md);
    expect(parsed.canRenderCards).toBe(true);
    const listCard = parsed.sections.flatMap(s => s.cards).find(c => c.kind === 'ordered_list');
    expect(listCard).toBeDefined();
    expect(listCard?.listItems?.length).toBe(3);
  });

  it('extracts labeled fields and formats identifiers with monospace backticks', () => {
    const text = 'Use: contracts, accounts\nPossible analytics: Net MRR churn rate';
    const { fields, remainingText } = extractLabeledFields(text);

    expect(fields.length).toBe(2);
    expect(fields[0].label).toBe('Use:');
    expect(fields[0].contentMarkdown).toBe('`contracts`, `accounts`');
    expect(fields[1].label).toBe('Possible analytics:');
    expect(fields[1].contentMarkdown).toBe('Net MRR churn rate');
    expect(remainingText).toBe('');
  });

  it('sanitizes dangerous HTML tags and links', () => {
    const maliciousMd = `
## Security Assessment
Here is text. <script>alert("xss")</script> <img src="x" onerror="alert(1)">

## Safe Links
[Safe Google](https://google.com) and [Dangerous JS](javascript:alert(1))
`;
    const parsed = parseMarkdownToCards(maliciousMd);
    expect(parsed.canRenderCards).toBe(true);
    const text = parsed.sections.flatMap(s => s.cards).map(c => c.fullMarkdown).join(' ');
    // Assert raw HTML nodes were dropped
    expect(text).not.toContain('<script>');
    expect(text).not.toContain('<img');
    // Assert javascript: link was rewritten to #
    expect(text).not.toContain('javascript:');
    expect(text).toContain('[Dangerous JS](#)');
    expect(text).toContain('https://google.com');
  });

  it('preserves plain lead-in text before the first heading', () => {
    const md = `
Here is an introductory sentence describing the query results before any sections.

## Analytics Domains
### Sales Performance
Use: invoices
Possible analytics: Monthly run rate

## Key Takeaways
Summary points.
`;
    const parsed = parseMarkdownToCards(md);
    expect(parsed.canRenderCards).toBe(true);
    expect(parsed.introText).toContain('Here is an introductory sentence describing the query results');
  });

  it('correctly structures multi-domain findings without splitting bullets or creating empty cards', () => {
    const md = `
## Executive Summary
An analysis of customer news, support SLA performance, and renewal tracking reveals a portfolio characterized by steady foundational health.

## Key Findings by Domain

### 1. Expansion Signals in Customer News
Qualitative tracking of account news indicates that risk indicators are currently outpacing growth opportunities:
- Retention Risks: 12.5% of accounts display qualitative "Risk" signals.
- Expansion Signals: 10.0% of accounts exhibit positive "Growth" indicators.
- Competitive & Relationship Dynamics: Additional signals include 7.5% for "Competitive" pressures.
- Compliance: Only 2.5% surfaced compliance-related news.

### 2. Retention Risks via Support SLA Breaches
Operational data highlights a critical split in support delivery performance:
- Support Health: Exactly 50% of the analyzed account base experienced an SLA Breach.

### 3. Renewal Status Distribution
Pipeline visibility for upcoming renewals requires immediate operational focus:
- Uninitiated Renewals: 95% of accounts are currently classified under the "Not Started" renewal status.
- Active Pipeline: Only 5% of accounts are currently marked as "Pending".

## Strategic Recommendations
1. **Initiate an Immediate Renewal Campaign**: Triage account base by renewal date.
2. **Launch a Support SLA Recovery Task Force**: Establish cross-functional remediation program.
3. **Cross-Reference News Risks**: Combine risk signals with SLA breaches.
`;

    const parsed = parseMarkdownToCards(md);
    expect(parsed.canRenderCards).toBe(true);

    const allCards = parsed.sections.flatMap(s => s.cards);

    // 1. Executive Summary should be full width
    const execSummary = allCards.find(c => c.title === 'Executive Summary');
    expect(execSummary).toBeDefined();
    expect(execSummary?.isFullWidth).toBe(true);

    // 2. "Key Findings by Domain" must NOT be an empty card, it should be a section label
    const emptyCategoryCard = allCards.find(c => c.title.toLowerCase().includes('findings by domain'));
    expect(emptyCategoryCard).toBeUndefined();
    expect(parsed.sections.some(s => s.sectionLabel?.includes('Findings by Domain'))).toBe(true);

    // 3. Point cards must contain their own bullets and NOT be split into "Key Items"
    const keyItemsCards = allCards.filter(c => c.title === 'Key Items');
    expect(keyItemsCards.length).toBe(0);

    const point1 = allCards.find(c => c.title.includes('Expansion Signals'));
    expect(point1).toBeDefined();
    expect(point1?.isFullWidth).toBe(false);
    expect(point1?.listItems?.length).toBe(4);

    const point2 = allCards.find(c => c.title.includes('Retention Risks'));
    expect(point2).toBeDefined();
    // Warning point inside the grid should be 2-column, not full-width
    expect(point2?.isFullWidth).toBe(false);
    expect(point2?.tone).toBe('warning');
    expect(point2?.listItems?.length).toBe(1);

    const point3 = allCards.find(c => c.title.includes('Renewal Status'));
    expect(point3).toBeDefined();
    expect(point3?.isFullWidth).toBe(false);
    expect(point3?.listItems?.length).toBe(2);

    // 4. Strategic recommendations should be a full-width ordered list card
    const recCard = allCards.find(c => c.title.includes('Recommendations'));
    expect(recCard).toBeDefined();
    expect(recCard?.kind).toBe('ordered_list');
    expect(recCard?.isFullWidth).toBe(true);
    expect(recCard?.listItems?.length).toBe(3);
  });

  it('correctly places domain cards in 2-column grid and list/conclusion cards full-width (Target Image 1-4)', () => {
    const md = `
I will map the available distribution tables into practical analytics areas.

## Distribution analytics opportunities

### Overall assessment
Based on the available tables, a strong analytics layer can be built.

### Analytics domains

#### Sales performance analytics
Use: sales_order, sales_order_item, invoice
Possible analytics: net sales, gross sales
Example dashboards: Monthly sales trend dashboard

#### Distributor performance analytics
Use: distributor, vw_sales_analysis
Possible analytics: distributor-wise sales volume
Example dashboards: Distributor scorecard

#### Payment, outstanding, and credit risk analytics
Use: invoice, payment_receipt
Possible analytics: total outstanding amount
Example dashboards: Outstanding and overdue dashboard

### High-value analytics to prioritize first
1. Sales performance dashboard: revenue, quantity
2. Outstanding and collection dashboard: overdue amount
3. Inventory health dashboard: stock below reorder level

### More advanced analytics possible
- Distributor segmentation using sales
- Retailer churn or inactivity detection
- SKU replenishment recommendations

### Conclusion
Overall, the data is strong enough to build a complete distribution intelligence system.
`;

    const parsed = parseMarkdownToCards(md);
    expect(parsed.canRenderCards).toBe(true);
    expect(parsed.introText).toContain('I will map the available distribution tables');

    const allCards = parsed.sections.flatMap(s => s.cards);

    // Overall assessment is full width
    const summary = allCards.find(c => c.title === 'Overall assessment');
    expect(summary?.isFullWidth).toBe(true);

    // Point cards in Analytics domains are 2-column (isFullWidth = false)
    const salesCard = allCards.find(c => c.title === 'Sales performance analytics');
    expect(salesCard?.isFullWidth).toBe(false);
    expect(salesCard?.fields?.length).toBe(3);

    const distCard = allCards.find(c => c.title === 'Distributor performance analytics');
    expect(distCard?.isFullWidth).toBe(false);

    // Warning point in grid is also 2-column
    const riskCard = allCards.find(c => c.title.includes('credit risk analytics'));
    expect(riskCard?.isFullWidth).toBe(false);
    expect(riskCard?.tone).toBe('warning');

    // High-value analytics is full-width ordered list
    const actionCard = allCards.find(c => c.title.includes('High-value analytics'));
    expect(actionCard?.isFullWidth).toBe(true);
    expect(actionCard?.kind).toBe('ordered_list');

    // Advanced analytics is full-width bullet list
    const advCard = allCards.find(c => c.title.includes('More advanced analytics'));
    expect(advCard?.isFullWidth).toBe(true);
    expect(advCard?.kind).toBe('bullet_list');

    // Conclusion is full-width
    const conclusion = allCards.find(c => c.title === 'Conclusion');
    expect(conclusion?.isFullWidth).toBe(true);
    expect(conclusion?.kind).toBe('conclusion');
  });
});
