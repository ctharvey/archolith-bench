import type { Bundle } from '../types';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const isExpiring = bundle.expiresAt && new Date(bundle.expiresAt) < new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

  return (
    <div className={css.bundleCard}>
      <div className={css.imageContainer}>
        {bundle.imageUrl ? (
          <img className={css.bundleImage} src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <div className={css.bundleImage} style={{ background: 'var(--surface-3)' }} />
        )}
        <div className={css.discountBadge}>-{bundle.discountPercent}%</div>
      </div>

      <div className={css.content}>
        <h3 className={css.bundleName}>{bundle.name}</h3>
        <p className={css.bundleDescription}>{bundle.description}</p>

        <div className={css.priceRow}>
          <span className={css.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
          <span className={css.bundlePrice}>${bundle.bundlePrice.toFixed(2)}</span>
          <span className={css.itemsCount}>{bundle.itemsCount} items</span>
        </div>

        {isExpiring && (
          <div className={css.expiryBadge}>
            Expires {new Date(bundle.expiresAt!).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  );
}
