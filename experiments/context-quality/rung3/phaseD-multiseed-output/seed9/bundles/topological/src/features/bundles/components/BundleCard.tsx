import type { Bundle } from '../types';
import { formatUSD } from '@/domain/formatters';
import { formatDiscount } from '../mappers';

interface BundleCardProps {
  bundle: Bundle;
}

export function BundleCard({ bundle }: BundleCardProps) {
  return (
    <div className="bundle-card">
      {bundle.imageUrl && (
        <img
          src={bundle.imageUrl}
          alt={bundle.name}
          className="bundle-card__image"
        />
      )}
      <div className="bundle-card__content">
        <h3 className="bundle-card__name">{bundle.name}</h3>
        <p className="bundle-card__description">{bundle.description}</p>
        <div className="bundle-card__pricing">
          <span className="bundle-card__original-price">
            {formatUSD(bundle.originalPrice)}
          </span>
          <span className="bundle-card__sale-price">
            {formatUSD(bundle.salePrice)}
          </span>
          <span className="bundle-card__discount">
            {formatDiscount(bundle.discountPercent)}
          </span>
        </div>
        <span className="bundle-card__item-count">
          {bundle.itemCount} {bundle.itemCount === 1 ? 'item' : 'items'}
        </span>
      </div>
    </div>
  );
}
