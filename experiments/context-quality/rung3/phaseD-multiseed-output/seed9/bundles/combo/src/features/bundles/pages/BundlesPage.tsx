import { useBundles } from '../hooks/useBundles';
import BundleGrid from '../components/BundleGrid';
import s from './BundlesPage.module.css';

export default function BundlesPage() {
  const { bundles, loading, error } = useBundles();

  if (loading) {
    return (
      <div className={s.page}>
        <div className={s.loading}>Loading bundles...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={s.page}>
        <div className={s.error}>{error}</div>
      </div>
    );
  }

  return (
    <div className={s.page}>
      <BundleGrid bundles={bundles} />
    </div>
  );
}
