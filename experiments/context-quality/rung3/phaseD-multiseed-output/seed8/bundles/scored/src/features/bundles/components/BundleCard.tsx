import { Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { bundleUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

function discountPercent(originalPrice: number | null, bundlePrice: number | null): number | null {
  if (originalPrice == null || bundlePrice == null || originalPrice <= 0) return null;
  return Math.round((1 - bundlePrice / originalPrice) * 100);
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
  bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const discount = discountPercent(bundle.originalPrice, bundle.bundlePrice);
  const [colorA, colorB] = gradColors(bundle.bundleName);

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const bundleHref = bundle.bundleId ? bundleUrl(bundle.bundleId, bundle.bundleName) : null;

  const content = (
    <>
      {/* Visual area */}
      <div className={s.visualArea} style={{ background: `linear-gradient(135deg, ${colorA}, ${colorB}), var(--bg-3)` }}>
        {bundle.imageUrl && (
          <img
            src={bundle.imageUrl}
            alt={bundle.bundleName}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        <div className={s.heroLabelWrap}>
          <div className={s.heroLabelText}>{bundle.bundleName}</div>
        </div>

        {/* Discount badge */}
        {discount != null && discount > 0 && (
          <div className={s.discountBadge}>
            <Pill variant="success-fill">Save {discount}%</Pill>
          </div>
        )}
      </div>

      {/* Info area */}
      <div className={s.infoArea}>
        <div className={s.bundleName} title={bundle.bundleName}>
          {bundle.bundleName}
        </div>

        <div className={`row ${s.metaRow}`}>
          {bundle.productCount != null && (
            <span className={`mono xs ${s.metaText}`}>{bundle.productCount} items</span>
          )}
          {bundle.category && (
            <span className={`mono xs ${s.metaText}`}>{bundle.category}</span>
          )}
        </div>

        {/* Price row */}
        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.bundlePrice}`}>
            {bundle.bundlePrice != null ? `$${bundle.bundlePrice.toFixed(2)}` : '—'}
          </span>
          {bundle.originalPrice != null && (
            <span className={s.originalPrice}>
              ${bundle.originalPrice.toFixed(2)}
            </span>
          )}
          {discount != null && discount > 0 && (
            <span className={`mono xs ${s.discountText}`}>
              -{discount}%
            </span>
          )}
        </div>

        {/* Savings row */}
        {bundle.originalPrice != null && bundle.bundlePrice != null && bundle.originalPrice > bundle.bundlePrice && (
          <div className={`row ${s.savingsRow}`}>
            <span className={`mono xs ${s.savingsLabel}`}>You save</span>
            <span className={`mono xs ${s.savingsValue}`}>
              ${(bundle.originalPrice - bundle.bundlePrice).toFixed(2)}
            </span>
          </div>
        )}
      </div>
    </>
  );

  if (bundleHref) {
    return (
      <a
        className={`box clickable-link ${s.wrapper}`}
        href={bundleHref}
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
