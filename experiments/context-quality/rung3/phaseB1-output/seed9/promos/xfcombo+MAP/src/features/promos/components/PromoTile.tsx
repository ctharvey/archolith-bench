import type { PromoCard } from '../types';
import s from './PromoTile.module.css';

interface PromoTileProps {
  promo: PromoCard;
}

export default function PromoTile({ promo }: PromoTileProps) {
  const year = promo.releaseYear || '—';

  return (
    <a href={promo.url} className={s.tile}>
      <div className={s.imageWrap}>
        {promo.image ? (
          <img src={promo.image} alt={promo.name} className={s.image} loading="lazy" />
        ) : (
          <div className={s.placeholder}>No image</div>
        )}
      </div>
      <div className={s.info}>
        <div className={s.name}>{promo.name}</div>
        <div className={s.meta}>
          <span className={s.year}>{year}</span>
          {promo.setName && <span className={s.set}>{promo.setName}</span>}
          {promo.number && <span className={s.number}>#{promo.number}</span>}
        </div>
        {promo.marketPrice != null && (
          <div className={s.price}>${promo.marketPrice.toFixed(2)}</div>
        )}
      </div>
    </a>
  );
}
