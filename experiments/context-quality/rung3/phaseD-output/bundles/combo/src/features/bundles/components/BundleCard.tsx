import { Pill } from '@/ui';
import { handleImageError } from '@/domain/dom-helpers';
import type { SealedProductPriceDto } from '@/data/apiClient';
import s from './BundleCard.module.css';

interface BundleProduct {
  productName: string;
  marketPrice: number | null;
  imageUrl?: string | null;
}

interface BundleCardProps {
  bundleName: string;
  bundlePrice: number;
  originalTotal: number;
  products: BundleProduct[];
  imageUrl?: string | null;
  href?: string | null;
}

function calcDiscount(original: number, bundle: number): number {
  if (original <= 0) return 0;
  return Math.round((1 - bundle / original) * 100);
}

function formatPrice(val: number): string {
  return `$${val.toFixed(2)}`;
}

export default function BundleCard({
  bundleName,
  bundlePrice,
  originalTotal,
  products,
  imageUrl,
  href,
}: BundleCardProps) {
  const discount = calcDiscount(originalTotal, bundlePrice);
  const savings = originalTotal - bundlePrice;

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const content = (
    <>
      <div className={s.visualArea} style={{ background: 'var(--bg-3)' }}>
        {imageUrl && (
          <img
            src={imageUrl}
            alt={bundleName}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        <div className={s.heroLabelWrap}>
          <div className={s.heroLabelText}>Bundle</div>
        </div>
        <div className={`row ${s.badgeRow}`}>
          <Pill variant="ink-fill">{discount}% off</Pill>
        </div>
      </div>

      <div className={s.infoArea}>
        <div className={s.productName} title={bundleName}>
          {bundleName}
        </div>

        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>{formatPrice(bundlePrice)}</span>
          <span className={`mono ${s.originalPrice}`}>{formatPrice(originalTotal)}</span>
          <span className={s.discountBadge}>-{discount}%</span>
        </div>

        <div className={`row ${s.savingsRow}`}>
          <span className={s.savingsLabel}>You save</span>
          <span className={s.savingsValue}>{formatPrice(savings)}</span>
        </div>

        <div className={s.productsList}>
          {products.map((p, i) => (
            <div key={i} className={s.productItem}>
              <span className={s.productItemName}>{p.productName}</span>
              <span className={s.productItemPrice}>
                {p.marketPrice != null ? formatPrice(p.marketPrice) : '—'}
              </span>
            </div>
          ))}
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
