/** A product bundle as rendered by the Bundles feature */
export interface Bundle {
  id: string;
  name: string;
  description: string;
  /** Original total price of items in bundle */
  originalPrice: number;
  /** Discounted bundle price */
  bundlePrice: number;
  /** Discount percent (e.g. 20 for 20% off) */
  discountPercent: number;
  /** Image URL for the bundle (null if unavailable) */
  imageUrl: string | null;
  /** Number of items in the bundle */
  itemCount: number;
  /** Whether the bundle is currently active/available */
  active: boolean;
}

/** Top-level page data returned by loadBundlesData() */
export interface BundlesPageData {
  bundles: Bundle[];
  totalBundles: number;
}
