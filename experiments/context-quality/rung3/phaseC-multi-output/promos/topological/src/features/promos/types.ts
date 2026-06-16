/** A promo card as rendered by Promos components */
export interface PromoCard {
  id: string;
  name: string;
  releaseYear: number;
  imageUrl: string | null;
  /** Set or series name (e.g. "Black Star Promos") */
  series: string;
  /** Card number within the promo series */
  cardNumber: string | null;
}

/** Top-level page data returned by loadPromosData() */
export interface PromosPageData {
  promos: PromoCard[];
  totalCount: number;
}
