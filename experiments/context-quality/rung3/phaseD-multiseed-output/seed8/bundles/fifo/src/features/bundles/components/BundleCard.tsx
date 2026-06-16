import type { Bundle } from '../types';
import { bundleToColor } from '../adapter';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
  onClick?: (bundle: Bundle) => void;
}

export default function BundleCard({ bundle, onClick }: BundleCardProps) {
  const color = bundleToColor(bundle.id);
  const isExpired = bundle.expiresAt ? new Date(bundle.expiresAt) < new Date() : false;
  const isActive = bundle.active && !isExpired;

  return (
    <div
      className={`${css.bundleCard} ${!isActive ? css.inactive : ''}`}
      onClick={() => onClick?.(bundle)}
      style={{ borderTop: `3px solid ${color}` }}
    >
      {bundle.discountPercent >= 20 && (
        <div className={css.badge}>Best Value</div>
      )}

      <div className={css.imageContainer}>
        {bundle.imageUrl ? (
          <img className={css.bundleImage} src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <div className={css.bundleImagePlaceholder}>📦</div>
        )}
      </div>

      <div className={css.content}>
        <h3 className={css.name}>{bundle.name}</h3>
        {bundle.description && (
          <p className={css.description}>{bundle.description}</p>
        )}

        <div className={css.priceRow}>
          <span className={css.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
          <span className={css.discountedPrice}>${bundle.discountedPrice.toFixed(2)}</span>
          <span className={css.discountBadge}>-{bundle.discountPercent}%</span>
        </div>

        {bundle.expiresAt && (
          <div className={css.expiry}>
            {isExpired ? 'Expired' : `Expires ${new Date(bundle.expiresAt).toLocaleDateString()}`}
          </div>
        )}

        {bundle.items.length > 0 && (
          <div className={css.itemsList}>
            {bundle.items.slice(0, 4).map((item, i) => (
              <span key={i} className={css.itemTag}>{item}</span>
            ))}
            {bundle.items.length > 4 && (
              <span className={css.itemTag}>+{bundle.items.length - 4} more</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
