import type { Bundle } from '../types';
import { bundleUrl } from '@/domain/slug';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  return (
    <a
      href={bundleUrl(bundle.id, bundle.name)}
      className={css.card}
      data-id={bundle.id}
    >
      {bundle.popular && (
        <div className={css.popularBadge}>Popular</div>
      )}

      <div className={css.imageContainer}>
        {bundle.imageUrl ? (
          <img className={css.image} src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <div className={css.placeholder} style={{ background: bundle.color }}>
            🎁
          </div>
        )}
      </div>

      <div className={css.content}>
        <div className={css.name}>{bundle.name}</div>
        {bundle.description && (
          <div className={css.description}>{bundle.description}</div>
        )}

        <div className={css.priceRow}>
          <span className={css.discountedPrice}>
            ${bundle.discountedPrice.toFixed(2)}
          </span>
          <span className={css.originalPrice}>
            ${bundle.originalPrice.toFixed(2)}
          </span>
          <span className={css.discountBadge}>
            -{bundle.discountPercent}%
          </span>
        </div>

        <div className={css.meta}>
          <span>{bundle.items} items</span>
          {bundle.tag && <span className={css.tag}>{bundle.tag}</span>}
        </div>
      </div>
    </a>
  );
}
