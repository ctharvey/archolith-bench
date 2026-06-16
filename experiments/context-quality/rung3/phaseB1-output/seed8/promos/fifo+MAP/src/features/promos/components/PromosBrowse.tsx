import { useMemo } from 'react';
import type { PromoCard } from '../types';
import s from './PromosBrowse.module.css';

interface PromosBrowseProps {
  promos: PromoCard[];
}

export default function PromosBrowse({ promos }: PromosBrowseProps) {
  const sorted = useMemo(() => {
    return [...promos].sort((a, b) => b.year - a.year || a.name.localeCompare(b.name));
  }, [promos]);

  return (
    <div className={s.promosBrowse}>
      <div className={s.header}>
        <h1 className={s.title}>Promos</h1>
        <p className={s.subtitle}>{promos.length} promo cards</p>
      </div>
      <div className={s.grid}>
        {sorted.map(promo => (
          <a key={promo.id} className={s.promoCard} href={`/promos/${promo.id}`}>
            <div className={s.imageWrapper}>
              {promo.imageUrl ? (
                <img className={s.image} src={promo.imageUrl} alt={promo.name} loading="lazy" />
              ) : (
                <span className={s.placeholder}>{promo.sym}</span>
              )}
            </div>
            <div className={s.info}>
              <span className={s.promoName}>{promo.name}</span>
              <span className={s.promoYear}>{promo.year}</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
