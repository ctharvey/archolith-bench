import type { Bundle } from './types';
import { formatUSD, pct } from '@/domain/formatters';

/** Derive discount percent from original and sale prices */
function calcDiscountPercent(original: number, sale: number): number {
  if (original <= 0) return 0;
  return Math.round((1 - sale / original) * 100);
}

/** Map a raw API bundle to the domain Bundle type */
export function mapBundle(raw: any): Bundle {
  const originalPrice = raw.originalPrice ?? 0;
  const salePrice = raw.salePrice ?? 0;
  return {
    id: raw.id ?? '',
    name: raw.name ?? '',
    description: raw.description ?? '',
    originalPrice,
    salePrice,
    discountPercent: calcDiscountPercent(originalPrice, salePrice),
    imageUrl: raw.imageUrl ?? null,
    itemCount: raw.itemCount ?? 0,
    active: raw.active ?? true,
  };
}

/** Format discount percent for display */
export function formatDiscount(pct: number): string {
  return `-${pct}%`;
}
