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
  topCardValue: number | null;
  topCardImageUrl: string | null;
  updatedAt: string;
  color: string;
}

export interface DecksV1Data {
  decks: DeckV1[];
  totalDecks: number;
  totalValue: number;
  avgValue: number;
}
