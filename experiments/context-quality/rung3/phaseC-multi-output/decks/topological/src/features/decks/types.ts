/** A deck as rendered by the Decks browse screen */
export interface Deck {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  uniqueCards: number;
  topCardName: string | null;
  topCardImageUrl: string | null;
  updatedAt: string | null;
  createdAt: string | null;
}

/** Top-level page data returned by loadDecksData() */
export interface DecksPageData {
  decks: Deck[];
  totalDecks: number;
  totalValue: number;
}
