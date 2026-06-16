import type { Bundle } from '../types';
import css from './BundleCard.module.css';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const formatPrice = (price: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);

  return (
    <div className={css.card}>
      <div className={css.imageWrapper}>
        {bundle.imageUrl ? (
          <img className={css.image} src={bundle.imageUrl} alt={bundle.name} loading="lazy" />
        ) : (
          <div className={css.placeholderImage}>📦</div>
        )}
      </div>
      <div className={css.content}>
        <div className={css.header}>
          <h3 className={css.name}>{bundle.name}</h3>
          <span className={css.discountBadge}>-{bundle.discountPercent}%</span>
        </div>
        {bundle.description && (
          <p className={css.description}>{bundle.description}</p>
        )}
        <div className={css.priceRow}>
          <span className={css.originalPrice}>{formatPrice(bundle.originalPrice)}</span>
          <span className={css.discountedPrice}>{formatPrice(bundle.discountedPrice)}</span>
          <span className={css.itemCount}>{bundle.items.length} items</span>
        </div>
      </div>
    </div>
  );
}
