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
  topCardImageUrl: string | null;
  color: string;
  updatedAt: string;
  winRate: string | null;
  tier: string | null;
}
