import { useMemo } from 'react';
import type { SealedProductPriceDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundlesGrid.module.css';

interface BundlesGridProps {
  products: SealedProductPriceDto[];
}

export default function BundlesGrid({ products }: BundlesGridProps) {
  const bundles = useMemo(() => {
    return products.filter(p => {
      const name = p.productName.toLowerCase();
      return (
        name.includes('bundle') ||
        name.includes('set of') ||
        name.includes('pack') ||
        name.includes('collection')
      );
    });
  }, [products]);

  if (bundles.length === 0) {
    return (
      <div className={s.empty}>
        <p>No bundles found.</p>
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {bundles.map(product => (
        <BundleCard key={product.tcgplayerId ?? product.productName} product={product} />
      ))}
    </div>
  );
}
