import { Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { sealedUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

interface BundleCardProps {
  bundle: BundleDto;
}

function discountPercent(original: number, current: number): number {
  if (original <= 0) return 0;
  return Math.round((1 - current / original) * 100);
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

export default function BundleCard({ bundle }: BundleCardProps) {
  const discount = bundle.originalPrice != null && bundle.currentPrice != null
    ? discountPercent(bundle.originalPrice, bundle.currentPrice)
    : null;

  const [colorA, colorB] = gradColors(bundle.name);

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const href = bundle.tcgplayerId ? sealedUrl(bundle.tcgplayerId, bundle.name) : null;

  const content = (
    <>
      <div className={s.visualArea} style={{ background: `linear-gradient(135deg, ${colorA}, ${colorB}), var(--bg-3)` }}>
        {bundle.imageUrl && (
          <img
            src={bundle.imageUrl}
            alt={bundle.name}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        <div className={`row ${s.badgeRow}`}>
          <Pill variant="ink-fill">Bundle</Pill>
          {discount != null && discount > 0 && (
            <Pill variant="green-fill">-{discount}%</Pill>
          )}
        </div>
      </div>
      <div className={s.infoArea}>
        <div className={s.productName} title={bundle.name}>
          {bundle.name}
        </div>
        <div className={`row ${s.metaRow}`}>
          {bundle.productCount != null && (
            <span className={`mono xs ${s.metaText}`}>{bundle.productCount} items</span>
          )}
          {bundle.setName && (
            <span className={`mono xs ${s.metaText}`}>{bundle.setName}</span>
          )}
        </div>
        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>
            {bundle.currentPrice != null ? `$${bundle.currentPrice.toFixed(2)}` : '—'}
          </span>
          {bundle.originalPrice != null && bundle.currentPrice != null && bundle.originalPrice > bundle.currentPrice && (
            <span className={`mono ${s.originalPrice}`}>
              ${bundle.originalPrice.toFixed(2)}
            </span>
          )}
          {discount != null && discount > 0 && (
            <span className={s.discountBadge}>-{discount}%</span>
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
