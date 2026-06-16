import type { PromoCard } from '../types';
import s from './PromoCard.module.css';

interface PromoCardProps {
  promo: PromoCard;
}

export default function PromoCard({ promo }: PromoCardProps) {
  return (
    <a href={promo.url} className={s.card} target="_blank" rel="noopener noreferrer">
      <div className={s.imageWrap}>
        {promo.image ? (
          <img src={promo.image} alt={promo.name} className={s.image} loading="lazy" />
        ) : (
          <div className={s.placeholder}>No image</div>
        )}
      </div>
      <div className={s.info}>
        <h3 className={s.name}>{promo.name}</h3>
        <div className={s.meta}>
          <span className={s.setName}>{promo.setName}</span>
          {promo.number && <span className={s.number}>#{promo.number}</span>}
        </div>
        <div className={s.details}>
          {promo.releaseYear && (
            <span className={s.year}>{promo.releaseYear}</span>
          )}
          {promo.rarity && (
            <span className={s.rarity}>{promo.rarity}</span>
          )}
        </div>
        {promo.marketPrice != null && (
          <div className={s.price}>
            ${promo.marketPrice.toFixed(2)}
            {promo.delta7d != null && (
              <span className={promo.delta7d >= 0 ? s.up : s.down}>
                {promo.delta7d >= 0 ? '+' : ''}{promo.delta7d.toFixed(1)}%
              </span>
            )}
          </div>
        )}
      </div>
    </a>
  );
}
