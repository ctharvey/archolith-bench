import type { Bundle } from '../types';
import { formatUSD } from '@/domain/formatters';
import { Box, Pill } from '@/ui';

interface BundleCardProps {
  bundle: Bundle;
}

export function BundleCard({ bundle }: BundleCardProps) {
  return (
    <Box className="bundle-card">
      <div className="bundle-card__image-wrapper">
        {bundle.imageUrl ? (
          <img
            src={bundle.imageUrl}
            alt={bundle.name}
            className="bundle-card__image"
          />
        ) : (
          <div className="bundle-card__image-placeholder">No Image</div>
        )}
        <Pill variant="accent" className="bundle-card__discount-badge">
          {bundle.discountPercent}% OFF
        </Pill>
      </div>
      <div className="bundle-card__content">
        <h3 className="bundle-card__name">{bundle.name}</h3>
        <p className="bundle-card__description">{bundle.description}</p>
        <div className="bundle-card__meta">
          <span className="bundle-card__item-count">{bundle.itemCount} items</span>
        </div>
        <div className="bundle-card__pricing">
          <span className="bundle-card__original-price">
            {formatUSD(bundle.originalPrice, { locale: true })}
          </span>
          <span className="bundle-card__bundle-price">
            {formatUSD(bundle.bundlePrice, { locale: true })}
          </span>
        </div>
      </div>
    </Box>
  );
}
