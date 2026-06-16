import { Pill } from '@/ui';
import type { SealedProductPriceDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { sealedUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

interface BundleCardProps {
  product: SealedProductPriceDto;
}

function discountPercent(marketPrice: number | null, highPrice: number | null): number | null {
  if (marketPrice == null || highPrice == null || highPrice <= 0) return null;
  const discount = ((highPrice - marketPrice) / highPrice) * 100;
  return Math.round(discount * 10) / 10;
}

function gradColors(name: string): [string, string] {
  const hash = name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const palettes: [string, string][] = [
    ['#7c3aed4d', '#3b82f64d'],
    ['#0596694d', '#06b6d44d'],
    ['#dc26264d', '#ea580c4d'],
    ['#9333ea4d', '#ec48994d'],
    ['#2563eb4d', '#7c3aed4d'],
    ['#0891b24d', '#0d94884d'],
  ];
  return palettes[hash % palettes.length];
}

export default function BundleCard({ product }: BundleCardProps) {
  const discount = discountPercent(product.marketPrice, product.highPrice);
  const savings = product.highPrice != null && product.marketPrice != null
    ? product.highPrice - product.marketPrice
    : null;
  const [colorA, colorB] = gradColors(product.productName);

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const productHref = product.tcgplayerId ? sealedUrl(product.tcgplayerId, product.productName) : null;

  const content = (
    <>
      <div className={s.visualArea} style={{ background: `linear-gradient(135deg, ${colorA}, ${colorB}), var(--bg-3)` }}>
        {product.imageUrl && (
          <img
            src={product.imageUrl}
            alt={product.productName}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        <div className={s.heroLabelWrap}>
          <div className={s.heroLabelText}>Bundle</div>
        </div>
        <div className={`row ${s.badgeRow}`}>
          {discount != null && (
            <Pill variant="success-fill">{discount}% off</Pill>
          )}
        </div>
      </div>

      <div className={s.infoArea}>
        <div className={s.productName} title={product.productName}>
          {product.productName}
        </div>

        <div className={`row ${s.metaRow}`}>
          {product.setId && (
            <span className={`mono xs ${s.metaText}`}>{product.setId}</span>
          )}
        </div>

        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>
            {product.marketPrice != null ? `$${product.marketPrice.toFixed(2)}` : '—'}
          </span>
          {product.highPrice != null && product.highPrice > (product.marketPrice ?? 0) && (
            <span className={s.originalPrice}>
              ${product.highPrice.toFixed(2)}
            </span>
          )}
          {discount != null && (
            <span className={s.discountBadge}>-{discount}%</span>
          )}
        </div>

        {savings != null && savings > 0 && (
          <div className={`row ${s.savingsRow}`}>
            <span>Save</span>
            <span className={s.savingsValue}>${savings.toFixed(2)}</span>
          </div>
        )}
      </div>
    </>
  );

  if (productHref) {
    return (
      <a
        className={`box clickable-link ${s.wrapper}`}
        href={productHref}
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
