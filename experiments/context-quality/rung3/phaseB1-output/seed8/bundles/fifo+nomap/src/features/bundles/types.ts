export interface Bundle {
  id: string;
  name: string;
  description: string;
  originalPrice: number;
  discountedPrice: number;
  discountPercent: number;
  imageUrl: string | null;
  items: string[];
  active: boolean;
}
