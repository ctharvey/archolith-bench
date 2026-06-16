export interface Deck {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  lastUpdated: string;
  color: string;
}

export interface DecksPageData {
  decks: Deck[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
