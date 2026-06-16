/** A promo card as rendered by Promos components */
export interface PromoCard {
  id: string;
  name: string;
  releaseYear: number;
  imageUrl: string | null;
  /** Set or series this promo belongs to */
  source: string;
  /** Current market price (null if unavailable) */
  price: number | null;
  /** 7-day price change percentage (null if unavailable) */
  d7: number | null;
  /** 30-day price change percentage (null if unavailable) */
  d30: number | null;
}

/** Top-level page data returned by loadPromosData() */
export interface PromosPageData {
  promos: PromoCard[];
  totalCount: number;
}
