import type { Bundle } from './types';
import { formatUSD, pct } from '@/domain/formatters';

/** Map a bundle for display — adds formatted strings */
export function mapBundleForDisplay(bundle: Bundle): Bundle & {
  originalPriceDisplay: string;
  bundlePriceDisplay: string;
  discountDisplay: string;
} {
  return {
    ...bundle,
    originalPriceDisplay: formatUSD(bundle.originalPrice, { locale: true }),
    bundlePriceDisplay: formatUSD(bundle.bundlePrice, { locale: true }),
    discountDisplay: pct(bundle.discountPercent),
  };
}
