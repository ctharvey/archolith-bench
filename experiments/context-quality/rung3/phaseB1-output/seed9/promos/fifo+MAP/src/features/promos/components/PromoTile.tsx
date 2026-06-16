import type { PromoCard } from '../types';
import s from './PromoTile.module.css';

interface PromoTileProps {
  promo: PromoCard;
}

export default function PromoTile({ promo }: PromoTileProps) {
  return (
    <a href={`/promos/${promo.id}`} className={s.promoTile}>
      <div className={s.imageContainer}>
        {promo.imageUrl ? (
          <img src={promo.imageUrl} alt={promo.name} className={s.promoImage} />
        ) : (
          <div className={s.placeholder} style={{ background: promo.color }}>
            {promo.sym}
          </div>
        )}
      </div>
      <div className={s.name}>{promo.name}</div>
      <div className={s.year}>{promo.year}</div>
    </a>
  );
}
