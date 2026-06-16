export interface Bundle {
  id: string;
  name: string;
  description: string;
  originalPrice: number;
  discountedPrice: number;
  discountPercent: number;
  imageUrl: string | null;
  items: number;
  popular: boolean;
  tag: string;
  color: string;
}
