import { Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { bundleUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

function discountPercent(original: number, current: number): number {
  if (original <= 0) return 0;
  return Math.round((1 - current / original) * 100);
}

interface BundleCardProps {
  bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const discount = bundle.originalPrice != null && bundle.originalPrice > 0
    ? discountPercent(bundle.originalPrice, bundle.price)
    : null;

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const href = bundle.id ? bundleUrl(bundle.id, bundle.name) : null;

  const content = (
    <>
      <div className={s.visualArea}>
        {bundle.imageUrl && (
          <img
            src={bundle.imageUrl}
            alt={bundle.name}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        {discount != null && discount > 0 && (
          <div className={s.discountBadge}>
            <Pill variant="green-fill">-{discount}%</Pill>
          </div>
        )}
      </div>
      <div className={s.infoArea}>
        <div className={s.productName} title={bundle.name}>
          {bundle.name}
        </div>
        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>
            ${bundle.price.toFixed(2)}
          </span>
          {bundle.originalPrice != null && bundle.originalPrice > bundle.price && (
            <span className={`mono ${s.originalPrice}`}>
              ${bundle.originalPrice.toFixed(2)}
            </span>
          )}
          {discount != null && discount > 0 && (
            <span className={s.discountPercent}>
              -{discount}%
            </span>
          )}
        </div>
        <div className={`row ${s.metaRow}`}>
          {bundle.productCount != null && (
            <span className={`mono xs ${s.metaText}`}>{bundle.productCount} items</span>
          )}
          {bundle.category && (
            <span className={`mono xs ${s.metaText}`}>{bundle.category}</span>
          )}
        </div>
      </div>
    </>
  );

  if (href) {
    return (
      <a
        className={`box clickable-link ${s.wrapper}`}
        href={href}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {content}
      </a>
    );
  }

  return (
    <div
      className={`box ${s.wrapper}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {content}
    </div>
  );
}
