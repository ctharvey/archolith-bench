import type { PromoSet } from '../usePromosData';
import s from './PromosCard.module.css';

interface PromosCardProps {
  promo: PromoSet;
}

export default function PromosCard({ promo }: PromosCardProps) {
  return (
    <div className={s.card}>
      <div className={s.logoWrap}>
        {promo.logoUrl ? (
          <img
            className={s.logo}
            src={promo.logoUrl}
            alt={`${promo.name} logo`}
            loading="lazy"
          />
        ) : (
          <div className={s.logoPlaceholder}>{promo.name.charAt(0)}</div>
        )}
      </div>
      <div className={s.info}>
        <h3 className={s.name}>{promo.name}</h3>
        <div className={s.meta}>
          <span className={s.year}>{promo.releaseYear}</span>
          <span className={s.separator}>·</span>
          <span className={s.cards}>{promo.cardCount} cards</span>
        </div>
        <div className={s.serie}>{promo.serie}</div>
      </div>
    </div>
  );
}
