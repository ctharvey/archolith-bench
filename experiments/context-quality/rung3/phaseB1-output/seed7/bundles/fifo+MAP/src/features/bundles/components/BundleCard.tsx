import type { Bundle } from '../types';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const formattedOriginal = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(bundle.originalPrice);

  const formattedDiscounted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(bundle.discountedPrice);

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
          <div className={css.placeholder}>📦</div>
        )}
      </div>
      <div className={css.content}>
        <div className={css.header}>
          <h3 className={css.name}>{bundle.name}</h3>
          <span className={css.discountBadge}>-{bundle.discountPercent}%</span>
        </div>
        <p className={css.description}>{bundle.description}</p>
        <div className={css.priceRow}>
          <span className={css.originalPrice}>{formattedOriginal}</span>
          <span className={css.discountedPrice}>{formattedDiscounted}</span>
        </div>
        <div className={css.itemsList}>
          {bundle.items.map((item, i) => (
            <span key={i} className={css.itemTag}>{item}</span>
          ))}
        </div>
        {expiresDate && (
          <div className={css.expiry}>Expires {expiresDate}</div>
        )}
      </div>
    </div>
  );
}
