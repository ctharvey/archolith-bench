import type { PromoDto } from '../promoTypes';
import PromoTile from './PromoTile';
import s from './PromosBody.module.css';

interface PromosBodyProps {
  promos: PromoDto[];
}

export default function PromosBody({ promos }: PromosBodyProps) {
  if (promos.length === 0) {
    return (
      <div className={s.empty}>
        <p>No promo sets match your filters.</p>
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
