import type { PromoCard } from '../types';
import css from './PromoCard.module.css';

interface PromoCardProps {
  promo: PromoCard;
}

export default function PromoCard({ promo }: PromoCardProps) {
  return (
    <a href={`/card/${promo.id}`} className={css.card}>
      <div className={css.imageWrapper}>
        {promo.imageUrl ? (
          <img className={css.image} src={promo.imageUrl} alt={promo.name} loading="lazy" />
        ) : (
          <div className={css.placeholder}>★</div>
        )}
      </div>
      <div className={css.info}>
        <div className={css.name}>{promo.name}</div>
        <div className={css.meta}>
          <span>{promo.set}</span>
          {promo.number && <span>#{promo.number}</span>}
          <span>{promo.rarity}</span>
        </div>
        <div className={css.year}>{promo.year}</div>
      </div>
    </a>
  );
}
