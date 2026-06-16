import type { SealedProductPriceDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: SealedProductPriceDto[];
}

export default function BundleGrid({ bundles }: BundleGridProps) {
  if (bundles.length === 0) {
    return (
      <div className={s.empty}>
        No bundles available right now.
      </div>
    );
  }

  return (
    <div>
      <div className={s.header}>
        <h2 className={s.title}>Bundles</h2>
        <span className={s.count}>{bundles.length} bundle{bundles.length !== 1 ? 's' : ''}</span>
      </div>
      <div className={s.grid}>
        {bundles.map((product) => (
          <BundleCard key={product.tcgplayerId ?? product.productName} product={product} />
        ))}
      </div>
    </div>
  );
}
