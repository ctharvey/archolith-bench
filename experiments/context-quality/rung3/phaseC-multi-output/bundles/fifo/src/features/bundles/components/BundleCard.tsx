import type { Bundle } from '../types';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const expiresDate = bundle.expiresAt
    ? new Date(bundle.expiresAt).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null;

  return (
    <div className={css.card}>
      <div className={css.imageWrapper}>
        {bundle.imageUrl ? (
          <img className={css.image} src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <div className={css.image} style={{ background: 'var(--surface-4)' }} />
        )}
        <span className={css.badge}>-{bundle.discountPercent}%</span>
      </div>
      <div className={css.content}>
        <h3 className={css.name}>{bundle.name}</h3>
        <p className={css.description}>{bundle.description}</p>
        <div className={css.priceRow}>
          <span className={css.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
          <span className={css.currentPrice}>${bundle.price.toFixed(2)}</span>
          <span className={css.discountBadge}>Save {bundle.discountPercent}%</span>
        </div>
        <span className={css.itemCount}>{bundle.items.length} items</span>
        {expiresDate && <span className={css.expires}>Expires {expiresDate}</span>}
      </div>
    </div>
  );
}
