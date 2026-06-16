// Add to existing apiClient

export interface BundleDto {
  id: string;
  name: string;
  tcgplayerId?: string;
  imageUrl?: string;
  originalPrice?: number;
  currentPrice?: number;
  productCount?: number;
  setName?: string;
}

export const apiClient = {
  // ... existing methods

  getBundles: async (): Promise<BundleDto[]> => {
    const response = await fetch('/api/bundles');
    if (!response.ok) {
      throw new Error(`Failed to fetch bundles: ${response.statusText}`);
    }
    return response.json();
  },
};
