/** A deck as rendered by the Decks browse screen */
export interface Deck {
  id: string;
  name: string;
  format: string;
  totalCards: number;
  marketValue: number;
  topCards: string[];
  lastUpdated: string;
}

/** Data returned by the decks data hook */
export interface DecksPageData {
  decks: Deck[];
  totalDecks: number;
  totalValue: number;
}
