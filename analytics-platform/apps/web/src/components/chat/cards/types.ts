export type CardKind =
  | 'summary'
  | 'point'
  | 'warning'
  | 'info'
  | 'ordered_list'
  | 'bullet_list'
  | 'conclusion'
  | 'table';

export type CardTone = 'primary' | 'warning' | 'info' | 'success' | 'neutral';

export interface LabeledFieldData {
  label: string; // e.g. "Use:" or "Possible analytics:"
  contentMarkdown: string; // Markdown text with code/bold tokens
}

export interface CardModel {
  id: string;
  kind: CardKind;
  tone: CardTone;
  title: string;
  leadParagraph?: string;
  fields?: LabeledFieldData[];
  listItems?: string[];
  rawTableMarkdown?: string;
  fullMarkdown: string;
  isFullWidth: boolean;
}

export interface CardSection {
  sectionLabel?: string;
  cards: CardModel[];
}

export interface ParsedAnswer {
  canRenderCards: boolean;
  introText?: string;
  sections: CardSection[];
  rawMarkdown: string;
}
