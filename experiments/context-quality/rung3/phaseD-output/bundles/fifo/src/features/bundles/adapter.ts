import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Bundle } from './types';

function calculateDiscount(original: number, discounted: number): number {
  if (original <= 0) return 0;
  return Math.round(((original - discounted) / original) * 100);
}

export async function loadBundles(signal?: AbortSignal): Promise<Bundle[]> {
  const data = await repo.bundles.list(signal);
  return data.map((b: any) => ({
    id: b.id,
    name: b.name,
    description: b.description ?? '',
    originalPrice: b.originalPrice,
    discountedPrice: b.discountedPrice,
    discountPercent: calculateDiscount(b.originalPrice, b.discountedPrice),
    imageUrl: b.imageUrl ? img(b.imageUrl) : null,
    items: b.items ?? [],
    active: b.active ?? true,
  }));
}
