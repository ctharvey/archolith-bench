export interface Deck {
  id: string;
  name: string;
  format: string;
  archetype: string;
  totalValue: number;
  totalValueFormatted: string;
  cardCount: number;
  topCardId: string | null;
  topCardImageUrl: string | null;
  color: string;
  released: string;
  winRate: string;
  winRateNum: number;
  popularity: string;
  popularityNum: number;
}
