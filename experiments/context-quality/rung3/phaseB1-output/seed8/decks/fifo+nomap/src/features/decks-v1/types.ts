export interface DeckV1 {
  id: string;
  name: string;
  format: string;
  archetype: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  uniqueCards: number;
  topCardName: string;
  topCardValue: number;
  topCardImageUrl: string | null;
  color: string;
  lastUpdated: string;
}
