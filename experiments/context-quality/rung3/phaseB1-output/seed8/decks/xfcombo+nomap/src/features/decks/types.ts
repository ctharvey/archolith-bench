export interface Deck {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  topCards: string[];
  lastUpdated: string;
}

export interface DecksPageData {
  decks: Deck[];
  totalValue: number;
  totalDecks: number;
}
