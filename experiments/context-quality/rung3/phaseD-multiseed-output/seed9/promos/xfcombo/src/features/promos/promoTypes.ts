export interface PromoDto {
  id: string;
  name: string;
  code: string;
  serie: string;
  releaseYear: number;
  cardCount: number;
  logoUrl: string | null;
  symbolUrl: string | null;
  primaryColor: string | null;
  secondaryColor: string | null;
}
