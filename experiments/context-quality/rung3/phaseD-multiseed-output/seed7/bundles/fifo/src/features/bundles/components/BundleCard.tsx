import type { Bundle } from '../types';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const { name, description, originalPrice, discountedPrice, discountPercent, imageUrl, items } = bundle;

  return (
    <div className="bundle-card">
      <div className="bundle-image-wrapper">
        {imageUrl ? (
          <img className="bundle-image" src={imageUrl} alt={name} loading="lazy" />
        ) : (
          <div className="bundle-placeholder">📦</div>
        )}
      </div>
      <div className="bundle-content">
        <h3 className="bundle-name">{name}</h3>
        {description && <p className="bundle-description">{description}</p>}
        <div className="bundle-price-row">
          <span className="bundle-original-price">${originalPrice.toFixed(2)}</span>
          <span className="bundle-discounted-price">${discountedPrice.toFixed(2)}</span>
          <span className="bundle-discount-badge">-{discountPercent}%</span>
        </div>
        <div className="bundle-item-count">{items.length} items</div>
      </div>
    </div>
  );
}
