/** A promo card as rendered by Promos components */
export interface PromoCard {
  id: string;
  name: string;
  releaseYear: number;
  imageUrl: string | null;
  /** Set or series this promo belongs to */
  source: string;
  /** Card number within the promo set */
  cardNumber: string | null;
  /** Rarity label if available */
  rarity: string | null;
}
