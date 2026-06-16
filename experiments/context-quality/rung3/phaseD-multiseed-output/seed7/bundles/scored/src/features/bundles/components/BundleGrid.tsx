import type { BundleDto } from '@/data/apiClient';
import BundleCard from './BundleCard';
import s from './BundleGrid.module.css';

interface BundleGridProps {
  bundles: BundleDto[];
  isLoading?: boolean;
}

export default function BundleGrid({ bundles, isLoading }: BundleGridProps) {
  if (isLoading) {
    return <div className={s.loading}>Loading bundles...</div>;
  }

  if (!bundles || bundles.length === 0) {
    return <div className={s.empty}>No bundles available right now.</div>;
  }

  return (
    <div className={s.grid}>
      {bundles.map((bundle) => (
        <BundleCard key={bundle.bundleId} bundle={bundle} />
      ))}
    </div>
  );
}
