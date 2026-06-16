export interface DecksV1Deck {
  id: string;
  name: string;
  format: string;
  archetype: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  uniqueCards: number;
  topCardId: string | null;
  color: string;
  sym: string;
  updatedAt: string;
  topCardImageUrl: string | null;
}
