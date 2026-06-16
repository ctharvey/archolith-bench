export interface PromoCard {
  id: string;
  name: string;
  image: string | null;
  url: string;
  setId: string;
  setName: string;
  rarity: string | null;
  number: string | null;
  releaseYear: string | null;
  marketPrice: number | null;
  marketPriceUrl: string | null;
  delta7d: number | null;
  delta30d: number | null;
}
