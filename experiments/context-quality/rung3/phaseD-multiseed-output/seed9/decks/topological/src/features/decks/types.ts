/** A deck as rendered by the Decks browse screen */
export interface DeckDto {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  updatedAt: string;
  createdAt: string;
}

/** Page data returned by loadDecks() */
export interface DecksPageData {
  decks: DeckDto[];
  totalDecks: number;
}
