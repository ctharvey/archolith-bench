import type { PromoCard } from '../types';
import { PromoCard as PromoCardComponent } from './PromoCard';
import { EmptyState } from '@/ui';

interface PromoGridProps {
  promos: PromoCard[];
}

export function PromoGrid({ promos }: PromoGridProps) {
  if (promos.length === 0) {
    return (
      <EmptyState
        title="No promos found"
        description="There are no promo cards to display at this time."
      />
    );
  }

  return (
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {promos.map((promo) => (
        <PromoCardComponent key={promo.id} promo={promo} />
      ))}
    </div>
  );
}
