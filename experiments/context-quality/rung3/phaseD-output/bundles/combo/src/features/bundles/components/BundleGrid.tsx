import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleItem {
  bundleName: string;
  bundlePrice: number;
  originalTotal: number;
  products: Array<{
    productName: string;
    marketPrice: number | null;
    imageUrl?: string | null;
  }>;
  imageUrl?: string | null;
  href?: string | null;
}

interface BundleGridProps {
  bundles: BundleItem[];
  title?: string;
}

export default function BundleGrid({ bundles, title }: BundleGridProps) {
  return (
    <section>
      {title && (
        <div className={s.header}>
          <h2 className={s.title}>{title}</h2>
          <span className={s.count}>{bundles.length} bundles</span>
        </div>
      )}
      <div className={s.grid}>
        {bundles.map((bundle, i) => (
          <BundleCard key={i} {...bundle} />
        ))}
      </div>
    </section>
  );
}
