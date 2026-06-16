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

/** API response shape for /api/decks */
export interface DecksApiResponse {
  decks: DeckSummary[];
  total: number;
}
