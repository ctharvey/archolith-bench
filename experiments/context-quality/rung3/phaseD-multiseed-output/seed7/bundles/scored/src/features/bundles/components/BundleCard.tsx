import { Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { bundleUrl } from '@/domain/slug';
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
  const { name, imageUrl, originalPrice, currentPrice, savings, productCount, bundleId } = bundle;
  const discount = discountPercent(originalPrice, currentPrice);
  const [colorA, colorB] = gradColors(name);

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const href = bundleUrl(bundleId, name);

  return (
    <a
      className={`box clickable-link ${s.wrapper}`}
      href={href}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Visual area */}
      <div className={s.visualArea} style={{ background: `linear-gradient(135deg, ${colorA}, ${colorB}), var(--bg-3)` }}>
        {imageUrl && (
          <img
            src={imageUrl}
            alt={name}
            className={s.heroImg}
            loading="lazy"
            onError={handleImageError}
          />
        )}
        <div className={s.discountBadge}>
          <Pill variant="green-fill">-{discount}%</Pill>
        </div>
      </div>

      {/* Info area */}
      <div className={s.infoArea}>
        <div className={s.bundleName} title={name}>
          {name}
        </div>

        <div className={s.metaRow}>
          {productCount != null && (
            <span className={`mono xs ${s.metaText}`}>{productCount} products</span>
          )}
        </div>

        <div className={s.priceRow}>
          <span className={`mono ${s.priceValue}`}>
            ${currentPrice.toFixed(2)}
          </span>
          <span className={`mono ${s.originalPrice}`}>
            ${originalPrice.toFixed(2)}
          </span>
          <span className={s.discountPercent}>
            -{discount}%
          </span>
        </div>

        {savings != null && savings > 0 && (
          <div className={s.savingsRow}>
            <span className={`mono xs ${s.savingsLabel}`}>You save</span>
            <span className={`mono xs ${s.savingsValue}`}>${savings.toFixed(2)}</span>
          </div>
        )}
      </div>
    </a>
  );
}
