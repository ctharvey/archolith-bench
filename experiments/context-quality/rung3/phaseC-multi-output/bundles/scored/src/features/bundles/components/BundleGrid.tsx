import type { BundleDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: BundleDto[];
  title?: string;
}

export default function BundleGrid({ bundles, title }: BundleGridProps) {
  return (
    <section>
      {title && (
        <div className={s.header}>
          <h2 className={s.title}>{title}</h2>
          <span className={`mono ${s.count}`}>{bundles.length} bundles</span>
        </div>
      )}
      <div className={s.grid}>
        {bundles.map((bundle) => (
          <BundleCard key={bundle.id} bundle={bundle} />
        ))}
      </div>
    </section>
  );
}
