/** A promo card as rendered by the Promos browse screen */
export interface PromoCard {
  id: string;
  name: string;
  releaseYear: number;
  imageUrl: string | null;
  /** Set/series name (e.g. "Black Star Promos") */
  series: string;
  /** Card number within the promo set */
  cardNumber: string | null;
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
