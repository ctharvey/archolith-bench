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
      className={css.bundleCard}
    >
      <div className={css.imageContainer}>
        {bundle.imageUrl ? (
          <img className={css.image} src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <span className={css.placeholder}>📦</span>
        )}
      </div>

      <div className={css.header}>
        <h3 className={css.name}>{bundle.name}</h3>
        <span className={css.discountBadge}>-{bundle.discountPercent}%</span>
      </div>

      <p className={css.description}>{bundle.description}</p>

      <div className={css.priceRow}>
        <span className={css.originalPrice}>${bundle.originalPrice.toFixed(2)}</span>
        <span className={css.discountedPrice}>${bundle.discountedPrice.toFixed(2)}</span>
      </div>

      <div className={css.itemsCount}>{bundle.items.length} items</div>
    </a>
  );
}
