export interface Bundle {
  id: string;
  name: string;
  description: string;
  imageUrl: string | null;
  originalPrice: number;
  bundlePrice: number;
  discountPercent: number;
  itemsCount: number;
  items: BundleItem[];
  active: boolean;
  expiresAt: string | null;
}

export interface BundleItem {
  id: string;
  name: string;
  imageUrl: string | null;
  quantity: number;
}
