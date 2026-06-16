export interface DeckDto {
  id: string;
  name: string;
  format: string;
  totalValue: number;
  cardCount: number;
  updatedAt: string;
}

export interface DecksPageData {
  decks: DeckDto[];
  totalDecks: number;
  totalValue: number;
}
