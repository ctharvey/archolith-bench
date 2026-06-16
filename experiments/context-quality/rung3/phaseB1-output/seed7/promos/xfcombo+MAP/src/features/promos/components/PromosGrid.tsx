import type { PromoCard } from '../types';
import PromoTile from './PromoTile';
import s from './PromosGrid.module.css';

interface PromosGridProps {
  promos: PromoCard[];
}

export default function PromosGrid({ promos }: PromosGridProps) {
  if (promos.length === 0) {
    return (
      <div className={s.empty}>
        <p className="muted">No promo cards match your filters.</p>
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {promos.map(promo => (
        <PromoTile key={promo.id} promo={promo} />
      ))}
    </div>
  );
}
