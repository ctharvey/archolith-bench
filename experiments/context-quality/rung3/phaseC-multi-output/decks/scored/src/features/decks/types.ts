export interface DeckSummary {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  lastUpdated: string;
  topCards: string[];
}

export interface DecksPageData {
  decks: DeckSummary[];
  totalDecks: number;
  totalValue: number;
  avgDeckValue: number;
}
