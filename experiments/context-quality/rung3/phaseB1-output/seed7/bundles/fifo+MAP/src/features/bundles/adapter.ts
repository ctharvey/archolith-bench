import { repo } from '@/data/repository';
import type { Bundle } from './types';

function calculateDiscount(original: number, discounted: number): number {
  if (original <= 0) return 0;
  return Math.round(((original - discounted) / original) * 100);
}

export async function loadBundles(signal?: AbortSignal): Promise<Bundle[]> {
  const bundles = await repo.bundles.list(signal);
  return bundles.map(b => ({
    ...b,
    discountPercent: calculateDiscount(b.originalPrice, b.discountedPrice),
  }));
}
