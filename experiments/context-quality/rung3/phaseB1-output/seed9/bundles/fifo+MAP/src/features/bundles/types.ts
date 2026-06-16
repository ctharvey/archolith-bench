export interface Bundle {
  id: string;
  name: string;
  description: string;
  imageUrl: string | null;
  originalPrice: number;
  discountedPrice: number;
  discountPercent: number;
  items: BundleItem[];
  active: boolean;
  expiresAt: string | null;
}

export interface BundleItem {
  productId: string;
  productName: string;
  productType: 'set' | 'sealed' | 'card';
  quantity: number;
}
