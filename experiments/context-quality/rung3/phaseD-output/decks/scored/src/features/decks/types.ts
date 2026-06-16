/** A deck with its market data */
export interface Deck {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  lastUpdated: string;
  color: string;
}

/** Top-level page data returned by loadDecksData() */
export interface DecksPageData {
  decks: Deck[];
  totalDecks: number;
  totalValue: number;
  avgDeckValue: number;
}
