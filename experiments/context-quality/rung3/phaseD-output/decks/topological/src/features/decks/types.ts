/** A deck as rendered by the Decks browse screen */
export interface DeckSummary {
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
  decks: DeckSummary[];
  totalDecks: number;
  totalValue: number;
}
