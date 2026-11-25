import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import type { Root, Content, Heading, Paragraph, List, Table } from 'mdast';
import type { CardModel, CardSection, ParsedAnswer, LabeledFieldData } from './types';
import { resolveHeadingTone } from './cardToneConfig';

/**
 * Extracts plain text from an mdast node and its descendants.
 * Drops any raw HTML tags for XSS safety.
 */
export function extractTextFromNode(node: any): string {
  if (!node) return '';
  if (node.type === 'text') return node.value;
  if (node.type === 'inlineCode' || node.type === 'code') return node.value;
  if (node.type === 'html') return ''; // Drop raw HTML tags completely
  if (Array.isArray(node.children)) {
    return node.children.map(extractTextFromNode).join('');
  }
  return '';
}

/**
 * Converts an mdast node back to standard sanitized Markdown text.
 * Strips raw HTML and ensures safe link protocols.
 */
export function nodeToMarkdown(node: any): string {
  if (!node) return '';
  switch (node.type) {
    case 'text':
      return node.value;
    case 'inlineCode':
      return `\`${node.value}\``;
    case 'code':
      return `\`\`\`${node.lang || ''}\n${node.value}\n\`\`\``;
    case 'strong':
      return `**${node.children.map(nodeToMarkdown).join('')}**`;
    case 'emphasis':
      return `*${node.children.map(nodeToMarkdown).join('')}*`;
    case 'link': {
      const url = String(node.url || '').trim();
      const isSafe = /^https?:\/\//i.test(url) || /^mailto:/i.test(url);
      const safeUrl = isSafe ? url : '#';
      return `[${node.children.map(nodeToMarkdown).join('')}](${safeUrl})`;
    }
    case 'paragraph':
      return node.children.map(nodeToMarkdown).join('');
    case 'html':
      // Drop raw HTML tags like <script> or <img onerror=...>
      return '';
    default:
      if (Array.isArray(node.children)) {
        return node.children.map(nodeToMarkdown).join('');
      }
      return '';
  }
}

/**
 * Detects labeled fields such as "Use: ...", "**Possible analytics:** ...", etc.
 */
const KNOWN_FIELD_LABELS = [
  'use',
  'possible analytics',
  'example dashboards',
  'metrics',
  'fields',
  'recommended actions',
  'source tables',
  'data sources',
  'key metrics',
  'dimensions',
];

export function extractLabeledFields(text: string): { fields: LabeledFieldData[]; remainingText: string } {
  const lines = text.split('\n');
  const fields: LabeledFieldData[] = [];
  const remainingLines: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    // Matches e.g. "**Use:** `contracts`" or "Use: contracts" or "- **Possible analytics:** Net MRR"
    const cleanedLine = trimmed.replace(/^[-*+]\s+/, '');
    const colonMatch = cleanedLine.match(/^(\*\*([^*]+)\*\*|([A-Za-z\s]+)):\s*(.+)$/);

    if (colonMatch) {
      const rawLabel = (colonMatch[2] || colonMatch[3] || '').trim();
      const content = colonMatch[4].trim();
      const lowerLabel = rawLabel.toLowerCase();

      if (KNOWN_FIELD_LABELS.some(l => lowerLabel === l || lowerLabel.startsWith(l))) {
        // Ensure table/column names in "Use:" or "Source tables:" have monospace backticks if missing
        let formattedContent = content;
        if (lowerLabel === 'use' || lowerLabel.includes('table') || lowerLabel.includes('source')) {
          formattedContent = formatMonospaceIdentifiers(content);
        }

        fields.push({
          label: rawLabel.endsWith(':') ? rawLabel : `${rawLabel}:`,
          contentMarkdown: formattedContent,
        });
        continue;
      }
    }

    remainingLines.push(line);
  }

  return { fields, remainingText: remainingLines.join('\n') };
}

/**
 * Automatically surrounds comma-separated SQL table/column identifiers with backticks
 * if they are plain alphanumeric tokens without spaces or backticks.
 */
export function formatMonospaceIdentifiers(text: string): string {
  // If already contains backticks, leave as-is
  if (text.includes('`')) return text;

  const parts = text.split(/,\s*/);
  const formatted = parts.map(part => {
    const trimmed = part.trim();
    if (/^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$/.test(trimmed)) {
      return `\`${trimmed}\``;
    }
    return part;
  });

  return formatted.join(', ');
}

/**
 * Checks whether an answer is eligible for Cards Mode.
 */
export function evaluateCardEligibility(markdown: string, metadata?: { isCodeIntel?: boolean }): boolean {
  if (!markdown || typeof markdown !== 'string') return false;

  // 1. Explicitly exempt Code Intelligence answers
  if (metadata?.isCodeIntel) return false;

  // 2. Explicitly exempt deterministic record lists
  if (markdown.trim().startsWith('Based on the verified database results')) return false;

  // 3. Count Markdown headings (## or ###)
  const headingMatches = markdown.match(/^#{1,4}\s+.+$/gm) || [];
  if (headingMatches.length >= 2) {
    return true;
  }

  // 4. Testable Activation Rule 3:
  // Heading followed by an ordered list of >= 3 items where each item starts with bold text and length >= 30
  const orderedListItems = markdown.match(/^\d+\.\s+\*\*[^*]+\*\*:.{20,}$/gm) || [];
  if (headingMatches.length >= 1 && orderedListItems.length >= 3) {
    return true;
  }

  return false;
}

/**
 * Parses raw markdown into structured CardSections and CardModels.
 */
export function parseMarkdownToCards(rawMarkdown: string, metadata?: { isCodeIntel?: boolean }): ParsedAnswer {
  if (!evaluateCardEligibility(rawMarkdown, metadata)) {
    return {
      canRenderCards: false,
      sections: [],
      rawMarkdown,
    };
  }

  let tree: Root;
  try {
    const processor = unified().use(remarkParse).use(remarkGfm);
    tree = processor.parse(rawMarkdown);
  } catch (err) {
    console.error('Failed to parse markdown AST for cards, falling back to standard markdown:', err);
    return {
      canRenderCards: false,
      sections: [],
      rawMarkdown,
    };
  }

  const children = tree.children;
  let introText = '';
  const sections: CardSection[] = [];
  let currentSection: CardSection = { cards: [] };
  let currentCard: Partial<CardModel> | null = null;
  let cardIndex = 0;

  // Helper to commit current card
  const commitCurrentCard = () => {
    if (currentCard && (currentCard.title || currentCard.leadParagraph || currentCard.fields?.length || currentCard.listItems?.length || currentCard.rawTableMarkdown)) {
      const card: CardModel = {
        id: `card-${cardIndex++}`,
        kind: currentCard.kind || 'point',
        tone: currentCard.tone || 'primary',
        title: currentCard.title || 'Analysis Point',
        leadParagraph: currentCard.leadParagraph,
        fields: currentCard.fields || [],
        listItems: currentCard.listItems,
        rawTableMarkdown: currentCard.rawTableMarkdown,
        fullMarkdown: currentCard.fullMarkdown || '',
        isFullWidth: Boolean(
          currentCard.isFullWidth ||
          currentCard.kind === 'summary' ||
          currentCard.kind === 'ordered_list' ||
          currentCard.kind === 'bullet_list' ||
          currentCard.kind === 'conclusion' ||
          currentCard.kind === 'table'
        ),
      };
      currentSection.cards.push(card);
      currentCard = null;
    }
  };

  // Helper to commit current section
  const commitCurrentSection = () => {
    commitCurrentCard();
    if (currentSection.cards.length > 0 || currentSection.sectionLabel) {
      sections.push(currentSection);
      currentSection = { cards: [] };
    }
  };

  let hasSeenFirstHeading = false;

  for (let i = 0; i < children.length; i++) {
    const node = children[i];

    if (!hasSeenFirstHeading) {
      if (node.type === 'heading') {
        hasSeenFirstHeading = true;
      } else {
        // Collect plain intro lead-in text preceding first heading
        const text = nodeToMarkdown(node);
        if (text.trim()) {
          introText = introText ? `${introText}\n\n${text}` : text;
        }
        continue;
      }
    }

    if (node.type === 'heading') {
      const headingNode = node as Heading;
      const headingText = extractTextFromNode(headingNode).trim();
      const { kind, tone } = resolveHeadingTone(headingText);

      // Section Category Label Detection:
      // (e.g. "Analytics Domains", "Key Findings by Domain", "Distribution analytics opportunities")
      // A heading is a category section label (rendered as text, NOT a card) if:
      // 1. It is not an explicit summary card ("Overall Assessment", "Executive Summary") or conclusion.
      // 2. AND either:
      //    a) The very next structural child in the AST is another heading (meaning this heading has no body of its own)
      //    b) Or the heading title matches grouping keywords (domain, domains, categories, areas, findings by, opportunities)
      const isSummaryOrConclusion = kind === 'summary' || kind === 'conclusion';

      let nextNode: (typeof children)[number] | undefined = undefined;
      for (let j = i + 1; j < children.length; j++) {
        const nextType = children[j].type;
        if (nextType === 'heading' || nextType === 'paragraph' || nextType === 'list' || nextType === 'table') {
          nextNode = children[j];
          break;
        }
      }

      const nextIsHeading = Boolean(nextNode && nextNode.type === 'heading');
      const isGroupingKeyword = /\b(domain|domains|categories|areas|findings by|opportunities)\b/i.test(headingText);

      if (!isSummaryOrConclusion && (nextIsHeading || isGroupingKeyword)) {
        commitCurrentSection();
        currentSection.sectionLabel = headingText;
        continue;
      }

      // Check if this heading represents an action plan or recommendations list
      const isRecommendationSection = /\b(recommendation|recommendations|action plan|prioritize|high-value analytics|roadmap|next steps)\b/i.test(headingText);

      // Check if this heading is a numbered point (e.g. "1. Expansion Signals...", "2. Retention Risks...")
      const isNumberedPoint = /^\d+\.\s+/.test(headingText);

      // Width calculation:
      // Summary, Conclusion, Action Roadmap, Standalone Table -> Full width (col-span-full)
      // Point cards (including numbered points, domain cards, warning points, info points) -> 2 columns (auto)
      // Standalone callout (e.g. "## Data Limitations" at root level with depth <= 2 and no sectionLabel) -> Full width
      let isFullWidth = false;
      if (isSummaryOrConclusion || isRecommendationSection) {
        isFullWidth = true;
      } else if (kind === 'warning' || kind === 'info') {
        isFullWidth = headingNode.depth <= 2 && !isNumberedPoint && !currentSection.sectionLabel;
      }

      // Otherwise start a new card
      commitCurrentCard();
      currentCard = {
        kind: isRecommendationSection ? 'ordered_list' : kind,
        tone: isRecommendationSection ? 'primary' : tone,
        title: headingText,
        fullMarkdown: `# ${headingText}\n\n`,
        isFullWidth,
        fields: [],
        listItems: [],
      };
    } else if (node.type === 'paragraph') {
      const paraText = nodeToMarkdown(node).trim();
      if (!currentCard) {
        // If no active card, create an info card or append to intro
        currentCard = {
          kind: 'info',
          tone: 'info',
          title: 'Note',
          leadParagraph: paraText,
          fullMarkdown: paraText,
          isFullWidth: false,
          fields: [],
          listItems: [],
        };
        continue;
      }

      currentCard.fullMarkdown = (currentCard.fullMarkdown || '') + `${paraText}\n\n`;

      // Check for labeled fields like "Use: ...", "Possible analytics: ..."
      const { fields, remainingText } = extractLabeledFields(paraText);
      if (fields.length > 0) {
        currentCard.fields = [...(currentCard.fields || []), ...fields];
        if (remainingText) {
          currentCard.leadParagraph = currentCard.leadParagraph
            ? `${currentCard.leadParagraph}\n\n${remainingText}`
            : remainingText;
        }
      } else {
        currentCard.leadParagraph = currentCard.leadParagraph
          ? `${currentCard.leadParagraph}\n\n${paraText}`
          : paraText;
      }
    } else if (node.type === 'list') {
      const listNode = node as List;
      const isOrdered = Boolean(listNode.ordered);
      const items: string[] = listNode.children.map(item => {
        return item.children.map(nodeToMarkdown).join('').trim();
      }).filter(Boolean);

      if (isOrdered) {
        // Numbered lists are structured action plans / sequential steps
        if (currentCard && (currentCard.kind === 'ordered_list' || !currentCard.leadParagraph)) {
          currentCard.kind = 'ordered_list';
          currentCard.isFullWidth = true;
          currentCard.listItems = items;
          currentCard.fullMarkdown = (currentCard.fullMarkdown || '') + items.map((it, idx) => `${idx + 1}. ${it}`).join('\n') + '\n\n';
          commitCurrentCard();
        } else if (currentCard) {
          // Ordered list inside active point card
          currentCard.listItems = [...(currentCard.listItems || []), ...items.map((it, idx) => `${idx + 1}. ${it}`)];
          currentCard.fullMarkdown = (currentCard.fullMarkdown || '') + items.map((it, idx) => `${idx + 1}. ${it}`).join('\n') + '\n\n';
        } else {
          commitCurrentCard();
          const listCard: CardModel = {
            id: `card-${cardIndex++}`,
            kind: 'ordered_list',
            tone: 'primary',
            title: 'Action Roadmap',
            listItems: items,
            fullMarkdown: items.map((it, idx) => `${idx + 1}. ${it}`).join('\n'),
            isFullWidth: true,
            fields: [],
          };
          currentSection.cards.push(listCard);
        }
      } else {
        // Unordered lists (- , * )
        const fieldList: LabeledFieldData[] = [];
        const nonFieldItems: string[] = [];

        for (const itemText of items) {
          const { fields } = extractLabeledFields(itemText);
          if (fields.length > 0) {
            fieldList.push(...fields);
          } else {
            nonFieldItems.push(itemText);
          }
        }

        if (currentCard) {
          if (fieldList.length > 0) {
            currentCard.fields = [...(currentCard.fields || []), ...fieldList];
          }

          // If currentCard had NO lead paragraph and NO fields (e.g. "### More advanced analytics possible"),
          // it represents a standalone list card!
          if (!currentCard.leadParagraph && (!currentCard.fields || currentCard.fields.length === 0) && nonFieldItems.length > 0) {
            currentCard.kind = 'bullet_list';
            currentCard.isFullWidth = true;
            currentCard.listItems = nonFieldItems;
            currentCard.fullMarkdown = (currentCard.fullMarkdown || '') + nonFieldItems.map(it => `- ${it}`).join('\n') + '\n\n';
            commitCurrentCard();
          } else {
            // Otherwise, these bullets belong inside the current point card (e.g. "1. Expansion Signals in Customer News")!
            if (nonFieldItems.length > 0) {
              currentCard.listItems = [...(currentCard.listItems || []), ...nonFieldItems];
            }
            currentCard.fullMarkdown = (currentCard.fullMarkdown || '') + nonFieldItems.map(it => `- ${it}`).join('\n') + '\n\n';
          }
        } else {
          commitCurrentCard();
          const bulletCard: CardModel = {
            id: `card-${cardIndex++}`,
            kind: 'bullet_list',
            tone: 'neutral',
            title: 'Key Items',
            listItems: nonFieldItems,
            fullMarkdown: nonFieldItems.map(it => `- ${it}`).join('\n'),
            isFullWidth: true,
            fields: [],
          };
          currentSection.cards.push(bulletCard);
        }
      }
    } else if (node.type === 'table') {
      // Embedded table between cards -> full-width card
      commitCurrentCard();
      const rawTableMd = nodeToMarkdown(node);
      currentCard = {
        kind: 'table',
        tone: 'neutral',
        title: 'Data Summary',
        rawTableMarkdown: rawTableMd,
        fullMarkdown: rawTableMd,
        isFullWidth: true,
      };
      commitCurrentCard();
    }
  }

  commitCurrentSection();

  // Validate that we have at least 2 cards or a multi-item structured action list
  const totalCards = sections.reduce((sum, s) => sum + s.cards.length, 0);
  const hasStructuredList = sections.some(s =>
    s.cards.some(c => (c.kind === 'ordered_list' || c.kind === 'bullet_list') && (c.listItems?.length || 0) >= 3)
  );
  if (totalCards < 2 && !hasStructuredList) {
    return {
      canRenderCards: false,
      sections: [],
      rawMarkdown,
    };
  }

  return {
    canRenderCards: true,
    introText,
    sections,
    rawMarkdown,
  };
}
