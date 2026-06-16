import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Bundle } from './types';

function calculateDiscount(original: number, discounted: number): number {
  if (original <= 0) return 0;
  return Math.round(((original - discounted) / original) * 100);
}

function bundleToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

export async function loadBundlesData(signal?: AbortSignal): Promise<{
  bundles: Bundle[];
  totalBundles: number;
  averageDiscount: number;
}> {
  const rawBundles = await repo.bundles.list(signal);
  
  const bundles: Bundle[] = rawBundles.map((b: any) => ({
    id: b.id,
    name: b.name,
    description: b.description || '',
    originalPrice: b.originalPrice,
    discountedPrice: b.discountedPrice,
    discountPercent: calculateDiscount(b.originalPrice, b.discountedPrice),
    imageUrl: b.imageUrl ? img(b.imageUrl) : null,
    items: b.items || [],
    active: b.active !== false,
    expiresAt: b.expiresAt || null,
  }));

  const totalBundles = bundles.length;
  const averageDiscount = bundles.length > 0
    ? Math.round(bundles.reduce((sum, b) => sum + b.discountPercent, 0) / bundles.length)
    : 0;

  return { bundles, totalBundles, averageDiscount };
}

export { bundleToColor };
