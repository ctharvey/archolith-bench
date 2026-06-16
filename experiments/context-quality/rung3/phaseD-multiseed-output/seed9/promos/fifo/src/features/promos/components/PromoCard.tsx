import type { PromoCard as PromoCardType } from '../types';
import css from './PromoCard.module.css';

interface PromoCardProps {
  promo: PromoCardType;
}

export default function PromoCard({ promo }: PromoCardProps) {
  return (
    <div className={css.card}>
      <div className={css.imageContainer}>
        {promo.imageUrl ? (
          <img className={css.image} src={promo.imageUrl} alt={promo.name} loading="lazy" />
        ) : (
          <span className={css.placeholder}>◆</span>
        )}
      </div>
      <div className={css.info}>
        <div className={css.name}>{promo.name}</div>
        <div className={css.meta}>
          <span className={css.year}>{promo.year > 0 ? promo.year : '—'}</span>
          <span>·</span>
          <span>{promo.set}</span>
          <span className={css.rarity}>{promo.rarity}</span>
        </div>
      </div>
    </div>
  );
}
