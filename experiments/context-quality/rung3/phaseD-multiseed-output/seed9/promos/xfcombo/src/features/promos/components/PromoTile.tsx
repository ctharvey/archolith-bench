import type { PromoDto } from '../promoTypes';
import s from './PromoTile.module.css';

interface PromoTileProps {
  promo: PromoDto;
}

export default function PromoTile({ promo }: PromoTileProps) {
  const yearLabel = promo.releaseYear > 0 ? promo.releaseYear.toString() : '—';

  return (
    <a href={`/promos/${promo.id}`} className={s.tile}>
      <div className={s.logoWrap}>
        {promo.logoUrl ? (
          <img src={promo.logoUrl} alt={promo.name} className={s.logo} />
        ) : (
          <div className={s.logoPlaceholder}>{promo.name.charAt(0)}</div>
        )}
      </div>
      <div className={s.info}>
        <h3 className={s.name}>{promo.name}</h3>
        <div className={s.meta}>
          <span className={s.year}>{yearLabel}</span>
          <span className={s.cardCount}>{promo.cardCount} cards</span>
        </div>
      </div>
    </a>
  );
}
