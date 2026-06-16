import type { BundleDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: BundleDto[];
}

export default function BundleGrid({ bundles }: BundleGridProps) {
  if (bundles.length === 0) {
    return <div className={s.empty}>No bundles available right now.</div>;
  }

  return (
    <div className={s.grid}>
      {bundles.map((bundle) => (
        <BundleCard key={bundle.id} bundle={bundle} />
      ))}
    </div>
  );
}
