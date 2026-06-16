import type { Bundle } from '../types';
import { bundleUrl } from '@/domain/slug';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(price);
}

function formatExpiry(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  if (diff <= 0) return 'Expired';
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
  if (days === 1) return '1 day left';
  return `${days} days left`;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const expiryText = formatExpiry(bundle.expiresAt);

  return (
    <a
      href={bundleUrl(bundle.id, bundle.name)}
      className={css.card}
    >
      <div className={css.imageWrapper}>
        {bundle.imageUrl ? (
          <img
            className={css.image}
            src={bundle.imageUrl}
            alt={bundle.name}
            loading="lazy"
          />
        ) : (
          <div className={css.placeholderImage}>📦</div>
        )}
      </div>

      {expiryText && (
        <div className={css.expiryBadge}>{expiryText}</div>
      )}

      <div className={css.content}>
        <div className={css.header}>
          <h3 className={css.name}>{bundle.name}</h3>
          <span className={css.discountBadge}>-{bundle.discountPercent}%</span>
        </div>

        {bundle.description && (
          <p className={css.description}>{bundle.description}</p>
        )}

        <div className={css.priceRow}>
          <span className={css.originalPrice}>
            {formatPrice(bundle.originalPrice)}
          </span>
          <span className={css.discountedPrice}>
            {formatPrice(bundle.discountedPrice)}
          </span>
        </div>

        {bundle.items.length > 0 && (
          <div className={css.itemsList}>
            {bundle.items.slice(0, 5).map((item, i) => (
              <span key={i} className={css.itemTag}>{item}</span>
            ))}
            {bundle.items.length > 5 && (
              <span className={css.itemTag}>+{bundle.items.length - 5} more</span>
            )}
          </div>
        )}
      </div>
    </a>
  );
}
