/** A deck as rendered by the Decks browse screen */
export interface DeckDto {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  uniqueCards: number;
  topCardName: string | null;
  topCardImageUrl: string | null;
  updatedAt: string;
}

/** Page data returned by loadDecksData() */
export interface DecksPageData {
  decks: DeckDto[];
  totalDecks: number;
  totalValue: number;
}
