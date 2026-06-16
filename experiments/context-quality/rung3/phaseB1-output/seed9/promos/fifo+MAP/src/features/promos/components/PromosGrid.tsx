import type { PromoCard } from '../types';
import PromoTile from './PromoTile';
import s from './PromosGrid.module.css';

interface PromosGridProps {
  promos: PromoCard[];
}

export default function PromosGrid({ promos }: PromosGridProps) {
  return (
    <div>
      <div className={s.header}>Promos</div>
      <div className={s.subheader}>{promos.length} promo cards</div>
      <div className={s.grid}>
        {promos.map(promo => (
          <PromoTile key={promo.id} promo={promo} />
        ))}
      </div>
    </div>
  );
}
