import type { PromoCard as PromoCardType } from '../types';
import { PromoCard } from './PromoCard';
import { EmptyState } from '@/ui/feedback';

interface PromoGridProps {
  promos: PromoCardType[];
}

export function PromoGrid({ promos }: PromoGridProps) {
  if (promos.length === 0) {
    return <EmptyState message="No promo cards found." />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {promos.map((promo) => (
        <PromoCard key={promo.id} promo={promo} />
      ))}
    </div>
  );
}
