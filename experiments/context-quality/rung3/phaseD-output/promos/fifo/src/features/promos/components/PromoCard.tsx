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
      <div className={css.imageWrapper}>
        {promo.imageUrl ? (
          <img
            className={css.image}
            src={promo.imageUrl}
            alt={promo.name}
            loading="lazy"
          />
        ) : (
          <div className={css.placeholder}>◆</div>
        )}
      </div>
      
      <div className={css.info}>
        <div className={css.name}>{promo.name}</div>
        <div className={css.meta}>
          <span>{promo.set}</span>
          <span>·</span>
          <span>{promo.rarity}</span>
          {promo.number !== '—' && (
            <>
              <span>·</span>
              <span>#{promo.number}</span>
            </>
          )}
        </div>
      </div>
      
      <div className={css.year}>
        {promo.year > 0 ? promo.year : '—'}
      </div>
    </a>
  );
}
