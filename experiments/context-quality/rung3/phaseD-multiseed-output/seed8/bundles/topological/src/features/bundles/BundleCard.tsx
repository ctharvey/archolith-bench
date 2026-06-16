import React from 'react';
import type { Bundle } from './types';
import { mapBundleForDisplay } from './mappers';
import { Box, KpiCard } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';

interface BundleCardProps {
  bundle: Bundle;
}

export const BundleCard: React.FC<BundleCardProps> = ({ bundle }) => {
  const display = mapBundleForDisplay(bundle);

  return (
    <Box className="bundle-card">
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
          <span className="bundle-card__original-price">{display.originalPriceDisplay}</span>
          <span className="bundle-card__bundle-price">{display.bundlePriceDisplay}</span>
          <span className="bundle-card__discount">{display.discountDisplay} off</span>
        </div>
        <div className="bundle-card__meta">
          <span>{bundle.itemCount} items</span>
        </div>
      </div>
    </Box>
  );
};
