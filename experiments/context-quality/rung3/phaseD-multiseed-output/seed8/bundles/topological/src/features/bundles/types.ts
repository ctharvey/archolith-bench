/** A product bundle as rendered by the Bundles feature */
export interface Bundle {
  id: string;
  name: string;
  description: string;
  /** Original total price of items if bought separately */
  originalPrice: number;
  /** Bundle price */
  bundlePrice: number;
  /** Discount percent (0-100) */
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
  totalCount: number;
}
