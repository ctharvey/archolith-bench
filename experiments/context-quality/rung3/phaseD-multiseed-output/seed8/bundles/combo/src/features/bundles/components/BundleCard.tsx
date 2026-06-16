import { Pill } from '@/ui';
import type { SealedProductPriceDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { sealedUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

function discountPercent(product: SealedProductPriceDto): number | null {
  if (product.marketPrice == null || product.highPrice == null || product.highPrice === 0) return null;
  const discount = ((product.highPrice - product.marketPrice) / product.highPrice) * 100;
  return Math.round(discount * 10) / 10;
}

function deltaText(val: number | null | undefined): { text: string; dir: 'up' | 'down' | 'flat' } {
  if (val == null) return { text: '—', dir: 'flat' };
  if (val > 0) return { text: `+${val.toFixed(1)}%`, dir: 'up' };
  if (val < 0) return { text: `${val.toFixed(1)}%`, dir: 'down' };
  return { text: '0.0%', dir: 'flat' };
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

interface BundleCardProps {
  product: SealedProductPriceDto;
}

export default function BundleCard({ product }: BundleCardProps) {
  const discount = discountPercent(product);
  const delta = deltaText(product.delta30d ?? product.delta7d);
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
        <div className={s.badgeRow}>
          <Pill variant="ink-fill">Bundle</Pill>
          {discount != null && (
            <Pill variant="ink-fill">{discount}% off</Pill>
          )}
        </div>
      </div>

      <div className={s.infoArea}>
        <div className={s.productName} title={product.productName}>
          {product.productName}
        </div>

        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>
            {product.marketPrice != null ? `$${product.marketPrice.toFixed(2)}` : '—'}
          </span>
          {product.highPrice != null && (
            <span className={s.highPrice}>
              ${product.highPrice.toFixed(2)}
            </span>
          )}
          <span className={`mono xs delta ${delta.dir}`}>
            {delta.text}
          </span>
        </div>

        {discount != null && (
          <div className={`row ${s.discountRow}`}>
            <span className={`mono xs ${s.discountLabel}`}>You save</span>
            <span className={`mono xs ${s.discountValue}`}>
              ${(product.highPrice! - product.marketPrice!).toFixed(2)}
            </span>
            <span className={`pill ${s.discountPill}`}>{discount}%</span>
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
