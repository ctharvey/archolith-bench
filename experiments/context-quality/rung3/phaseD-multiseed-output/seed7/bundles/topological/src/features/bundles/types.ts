/** A product bundle as rendered by the Bundles feature */
export interface Bundle {
  id: string;
  name: string;
  description: string;
  /** Original total price of items in bundle */
  originalPrice: number;
  /** Bundle sale price */
  salePrice: number;
  /** Discount percent (derived from originalPrice and salePrice) */
  discountPercent: number;
  /** Number of items in the bundle */
  itemCount: number;
  /** Image URL for the bundle (null if unavailable) */
  imageUrl: string | null;
  /** Whether the bundle is currently active/available */
  active: boolean;
}

/** API response shape for bundles list endpoint */
export interface BundlesApiResponse {
  bundles: Bundle[];
  total: number;
}
