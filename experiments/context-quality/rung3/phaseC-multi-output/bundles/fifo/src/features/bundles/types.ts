export interface Bundle {
  id: string;
  name: string;
  description: string;
  price: number;
  originalPrice: number;
  discountPercent: number;
  imageUrl: string | null;
  items: string[];
  active: boolean;
  expiresAt: string | null;
}
