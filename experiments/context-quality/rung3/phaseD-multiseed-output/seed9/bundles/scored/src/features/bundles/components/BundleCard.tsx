import { Pill } from '@/ui';
import type { BundleDto } from '@/data/apiClient';
import { handleImageError } from '@/domain/dom-helpers';
import { bundleUrl } from '@/domain/slug';
import s from './BundleCard.module.css';

function deltaText(val: number | null | undefined): { text: string; dir: 'up' | 'down' | 'flat' } {
  if (val == null) return { text: '—', dir: 'flat' };
  if (val > 0) return { text: `+${val.toFixed(1)}%`, dir: 'up' };
  if (val < 0) return { text: `${val.toFixed(1)}%`, dir: 'down' };
  return { text: '0.0%', dir: 'flat' };
}

interface BundleCardProps {
  bundle: BundleDto;
}

export default function BundleCard({ bundle }: BundleCardProps) {
  const delta = deltaText(bundle.delta30d ?? bundle.delta7d);
  const discountPercent = bundle.originalPrice && bundle.price
    ? Math.round((1 - bundle.price / bundle.originalPrice) * 100)
    : null;

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = 'translateY(-2px)';
    e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)';
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    e.currentTarget.style.transform = '';
    e.currentTarget.style.boxShadow = '';
  };

  const href = bundle.slug ? bundleUrl(bundle.slug) : null;

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
        <div className={`row ${s.badgeRow}`}>
          <Pill variant="ink-fill">Bundle</Pill>
          {bundle.productCount != null && (
            <Pill variant="ink-fill">{bundle.productCount} items</Pill>
          )}
        </div>
        {discountPercent != null && discountPercent > 0 && (
          <div className={s.discountBadge}>-{discountPercent}%</div>
        )}
      </div>
      <div className={s.infoArea}>
        <div className={s.bundleName} title={bundle.name}>
          {bundle.name}
        </div>
        <div className={`row ${s.metaRow}`}>
          {bundle.setName && (
            <span className={`mono xs ${s.metaText}`}>{bundle.setName}</span>
          )}
          {bundle.productCount != null && (
            <span className={`mono xs ${s.metaText}`}>{bundle.productCount} products</span>
          )}
        </div>
        <div className={`row ${s.priceRow}`}>
          <span className={`mono ${s.priceValue}`}>
            {bundle.price != null ? `$${bundle.price.toFixed(2)}` : '—'}
          </span>
          {bundle.originalPrice != null && bundle.originalPrice > (bundle.price ?? 0) && (
            <span className={s.originalPrice}>
              ${bundle.originalPrice.toFixed(2)}
            </span>
          )}
          <span className={`mono xs delta ${delta.dir}`}>
            {delta.text}
          </span>
        </div>
        {bundle.productCount != null && (
          <span className={`mono xs ${s.productCount}`}>
            {bundle.productCount} item{bundle.productCount !== 1 ? 's' : ''}
          </span>
        )}
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
