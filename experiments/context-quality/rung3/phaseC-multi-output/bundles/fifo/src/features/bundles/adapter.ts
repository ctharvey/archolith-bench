import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Bundle } from './types';

function calculateDiscount(originalPrice: number, price: number): number {
  if (originalPrice <= 0) return 0;
  return Math.round(((originalPrice - price) / originalPrice) * 100);
}

export async function loadBundlesData(signal?: AbortSignal): Promise<{
  bundles: Bundle[];
  totalBundles: number;
}> {
  const bundles = await repo.bundles.list(signal);
  const enriched = bundles.map(b => ({
    ...b,
    discountPercent: calculateDiscount(b.originalPrice, b.price),
    imageUrl: b.imageUrl ? img(b.imageUrl) : null,
  }));
  return { bundles: enriched, totalBundles: enriched.length };
}
