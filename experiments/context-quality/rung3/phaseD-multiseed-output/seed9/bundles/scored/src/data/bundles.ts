import type { BundleDto } from '@/data/apiClient';

const BUNDLES_ENDPOINT = '/api/bundles';

export async function fetchBundles(): Promise<BundleDto[]> {
  const response = await fetch(BUNDLES_ENDPOINT);
  if (!response.ok) {
    throw new Error(`Failed to fetch bundles: ${response.statusText}`);
  }
  const data: BundleDto[] = await response.json();
  return data;
}
