import type { SealedProductPriceDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleGridProps {
  products: SealedProductPriceDto[];
  title?: string;
}

export default function BundleGrid({ products, title = 'Bundles' }: BundleGridProps) {
  if (products.length === 0) {
    return (
      <div className={s.empty}>
        <p>No bundles available right now.</p>
      </div>
    );
  }

  return (
    <section>
      <div className={s.header}>
        <h2 className={s.title}>{title}</h2>
        <span className={s.count}>{products.length} bundle{products.length !== 1 ? 's' : ''}</span>
      </div>
      <div className={s.grid}>
        {products.map((product) => (
          <BundleCard key={product.tcgplayerId ?? product.productName} product={product} />
        ))}
      </div>
    </section>
  );
}
