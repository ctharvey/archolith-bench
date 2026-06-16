import type { PromoCard } from '../types';
import { setUrl } from '@/domain/slug';
import s from './PromoCard.module.css';

interface PromoCardProps {
  promo: PromoCard;
}

export default function PromoCard({ promo }: PromoCardProps) {
  return (
    <a
      href={setUrl(promo.id, promo.name)}
      className={s.card}
    >
      <div className={s.imageWrapper}>
        {promo.imageUrl ? (
          <img
            src={promo.imageUrl}
            alt={promo.name}
            className={s.image}
            loading="lazy"
          />
        ) : (
          <div className={s.placeholder}>◆</div>
        )}
      </div>
      
      <div className={s.info}>
        <h3 className={s.name}>{promo.name}</h3>
        <div className={s.meta}>
          <span className={s.metaItem}>
            #{promo.number}
          </span>
          <span className={s.metaItem}>
            {promo.set}
          </span>
          <span className={s.metaItem}>
            {promo.rarity}
          </span>
        </div>
      </div>
      
      <div className={s.year}>
        {promo.year}
      </div>
    </a>
  );
}
