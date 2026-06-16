export interface DeckSummary {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  topCards: Array<{ name: string; price: number }>;
  lastUpdated: string;
}

export interface DecksPageData {
  decks: DeckSummary[];
  totalDecks: number;
  totalValue: number;
  avgDeckValue: number;
}
