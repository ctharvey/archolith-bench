import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Bundle } from './types';

/** Derive a stable color from bundle id (OKLCH hue range) */
function bundleToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

/** Load all bundles data */
export async function loadBundlesData(signal?: AbortSignal): Promise<{
  bundles: Bundle[];
  totalSavings: number;
}> {
  const data = await repo.market.bundles(signal);
  const bundles: Bundle[] = data.map((b: any) => ({
    id: b.id,
    name: b.name,
    description: b.description ?? '',
    originalPrice: b.originalPrice,
    discountedPrice: b.discountedPrice,
    discountPercent: Math.round((1 - b.discountedPrice / b.originalPrice) * 100),
    imageUrl: b.imageUrl ? img(b.imageUrl) : null,
    items: b.items ?? 0,
    popular: b.popular ?? false,
    tag: b.tag ?? '',
    color: bundleToColor(b.id),
  }));
  const totalSavings = bundles.reduce((sum, b) => sum + (b.originalPrice - b.discountedPrice), 0);
  return { bundles, totalSavings };
}
