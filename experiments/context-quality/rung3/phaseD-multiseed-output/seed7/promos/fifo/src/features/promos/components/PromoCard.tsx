import type { PromoCard } from '../types';
import css from './PromoCard.module.css';

interface PromoCardProps {
  card: PromoCard;
}

export default function PromoCard({ card }: PromoCardProps) {
  return (
    <div className={css.card}>
      <div className={css.imageWrapper}>
        {card.imageUrl ? (
          <img className={css.image} src={card.imageUrl} alt={card.name} loading="lazy" />
        ) : (
          <div className={css.placeholder}>◆</div>
        )}
      </div>
      <div className={css.info}>
        <div className={css.name}>{card.name}</div>
        <div className={css.meta}>
          <span>{card.set} · #{card.number}</span>
          <span className={css.year}>{card.year}</span>
        </div>
      </div>
    </div>
  );
}
