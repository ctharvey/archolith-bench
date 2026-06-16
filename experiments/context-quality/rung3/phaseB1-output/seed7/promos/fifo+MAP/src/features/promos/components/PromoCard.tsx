import type { PromoCard } from '../types';
import css from './PromoCard.module.css';

interface PromoCardProps {
  card: PromoCard;
}

export default function PromoCard({ card }: PromoCardProps) {
  return (
    <div className={css.promoCard}>
      <div className={css.imageWrapper}>
        {card.imageUrl ? (
          <img className={css.image} src={card.imageUrl} alt={card.name} loading="lazy" />
        ) : (
          <div className={css.placeholder}>No Image</div>
        )}
      </div>
      <div className={css.info}>
        <div className={css.name}>{card.name}</div>
        <div className={css.meta}>
          <span className={css.year}>{card.year}</span>
          <span>·</span>
          <span className={css.rarity}>{card.rarity}</span>
        </div>
      </div>
    </div>
  );
}
