import type { Bundle } from '../types';
import { formatUSD } from '@/domain/formatters';
import { Box, KpiCard } from '@/ui';

interface BundleCardProps {
  bundle: Bundle;
  onClick?: () => void;
}

export function BundleCard({ bundle, onClick }: BundleCardProps) {
  const discountLabel = `${bundle.discountPercent}% OFF`;

  return (
    <Box
      as="article"
      className="bundle-card"
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {bundle.imageUrl && (
        <img
          src={bundle.imageUrl}
          alt={bundle.name}
          className="bundle-card__image"
          loading="lazy"
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
          <span className="bundle-card__discount-badge">{discountLabel}</span>
        </div>
        <KpiCard
          label="Items"
          value={bundle.itemCount}
          size="sm"
        />
      </div>
    </Box>
  );
}
