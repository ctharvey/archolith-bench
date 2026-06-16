export interface DeckData {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  topCards: { name: string; price: number }[];
  lastUpdated: string;
}

export interface DecksPageData {
  decks: DeckData[];
  totalDecks: number;
  totalValue: number;
  avgDeckValue: number;
}
