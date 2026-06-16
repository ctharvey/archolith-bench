import type { PromoSet } from '../usePromosData';
import PromosCard from './PromosCard';
import s from './PromosBody.module.css';

interface PromosBodyProps {
  promos: PromoSet[];
}

export default function PromosBody({ promos }: PromosBodyProps) {
  if (promos.length === 0) {
    return (
      <div className={s.empty}>
        No promo sets match your filters.
      </div>
    );
  }

  return (
    <div className={s.grid}>
      {promos.map(promo => (
        <PromosCard key={promo.id} promo={promo} />
      ))}
    </div>
  );
}
