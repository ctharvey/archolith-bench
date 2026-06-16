// Add BundleDto type (assumed to be added to existing apiClient types)
export interface BundleDto {
  id: string;
  slug: string;
  name: string;
  description?: string;
  imageUrl?: string;
  price: number | null;
  originalPrice: number | null;
  productCount: number | null;
  setName?: string;
  delta7d?: number | null;
  delta30d?: number | null;
  createdAt?: string;
}
