import type { Bundle } from '../types';

interface BundleCardProps {
  bundle: Bundle;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  return (
    <div className="bundle-card">
      <div className="bundle-image-wrapper">
        {bundle.imageUrl ? (
          <img className="bundle-image" src={bundle.imageUrl} alt={bundle.name} />
        ) : (
          <div className="bundle-placeholder">📦</div>
        )}
      </div>
      <div className="bundle-content">
        <h3 className="bundle-name">{bundle.name}</h3>
        {bundle.description && (
          <p className="bundle-description">{bundle.description}</p>
        )}
        <div className="bundle-price-row">
          <span className="bundle-original-price">${bundle.originalPrice.toFixed(2)}</span>
          <span className="bundle-discounted-price">${bundle.discountedPrice.toFixed(2)}</span>
          <span className="bundle-discount-badge">-{bundle.discountPercent}%</span>
        </div>
        {bundle.items.length > 0 && (
          <div className="bundle-items-list">
            {bundle.items.map((item, i) => (
              <span key={i} className="bundle-item-tag">{item}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
