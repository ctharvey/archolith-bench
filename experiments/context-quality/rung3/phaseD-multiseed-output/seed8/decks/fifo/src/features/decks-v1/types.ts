export interface DeckV1 {
  id: string;
  name: string;
  format: string;
  archetype: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  uniqueCards: number;
  topCardId: string | null;
  topCardName: string | null;
  color: string;
  updatedAt: string;
}

export interface DecksV1Data {
  decks: DeckV1[];
  totalDecks: number;
  totalValue: number;
}
