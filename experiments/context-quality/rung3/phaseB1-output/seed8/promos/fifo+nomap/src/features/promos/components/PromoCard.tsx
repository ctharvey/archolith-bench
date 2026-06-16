import type { PromoCard } from '../types';
import { setUrl } from '@/domain/slug';
import css from './PromoCard.module.css';

interface PromoCardProps {
  promo: PromoCard;
}

export default function PromoCard({ promo }: PromoCardProps) {
  return (
    <a
      href={setUrl(promo.id, promo.name)}
      className={css.card}
    >
      <div className={css.imageContainer}>
        {promo.imageUrl ? (
          <img
            className={css.image}
            src={promo.imageUrl}
            alt={promo.name}
            loading="lazy"
          />
        ) : (
          <div className={css.placeholder}>
            {promo.name.charAt(0)}
          </div>
        )}
      </div>
      <div className={css.info}>
        <div className={css.name}>{promo.name}</div>
        <div className={css.meta}>
          <span>{promo.set}</span>
          <span>#{promo.number}</span>
        </div>
        <div className={css.year}>{promo.year}</div>
      </div>
    </a>
  );
}
