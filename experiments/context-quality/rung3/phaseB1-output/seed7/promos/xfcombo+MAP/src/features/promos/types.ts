export interface PromoCard {
  id: string;
  name: string;
  image: string | null;
  url: string;
  setId: string;
  setName: string | null;
  rarity: string | null;
  number: string | null;
  releaseYear: number | null;
  marketPrice: number | null;
  delta7d: number | null;
  delta30d: number | null;
}
