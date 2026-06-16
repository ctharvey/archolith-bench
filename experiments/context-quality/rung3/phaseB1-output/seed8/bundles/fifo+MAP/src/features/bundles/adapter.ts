import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Bundle, BundleItem } from './types';

function calculateDiscount(original: number, bundle: number): number {
  if (original <= 0) return 0;
  return Math.round((1 - bundle / original) * 100);
}

export async function loadBundles(signal?: AbortSignal): Promise<Bundle[]> {
  const rawBundles = await repo.bundles.list(signal);
  
  return rawBundles.map((raw: any) => {
    const items: BundleItem[] = (raw.items || []).map((item: any) => ({
      id: item.id,
      name: item.name,
      imageUrl: item.imageUrl ? img(item.imageUrl) : null,
      quantity: item.quantity || 1,
    }));

    const originalPrice = items.reduce((sum, item) => sum + (item.quantity * (raw.itemPrices?.[item.id] || 0)), 0);
    const bundlePrice = raw.bundlePrice || 0;

    return {
      id: raw.id,
      name: raw.name,
      description: raw.description || '',
      imageUrl: raw.imageUrl ? img(raw.imageUrl) : null,
      originalPrice,
      bundlePrice,
      discountPercent: calculateDiscount(originalPrice, bundlePrice),
      itemsCount: items.length,
      items,
      active: raw.active !== false,
      expiresAt: raw.expiresAt || null,
    };
  });
}
