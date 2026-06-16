/** A promo card as rendered by Promos components */
export interface PromoCard {
  id: string;
  name: string;
  releaseYear: number;
  imageUrl: string | null;
  /** Set name or series this promo belongs to */
  source: string;
  /** Current market price (FMV) */
  fmv: number | null;
  /** 7-day price change percentage */
  d7: number | null;
  /** 30-day price change percentage */
  d30: number | null;
  /** 90-day price change percentage */
  d90: number | null;
}

/** Top-level page data returned by loadPromosData() */
export interface PromosPageData {
  promos: PromoCard[];
  totalCount: number;
}
