import type { PromoCard } from './types';
import { Box } from '@/ui';
import { formatDate } from '@/domain/formatters';

interface PromoCardItemProps {
  promo: PromoCard;
}

export function PromoCardItem({ promo }: PromoCardItemProps) {
  return (
    <Box padding="md" border="subtle" borderRadius="md">
      {promo.imageUrl && (
        <img
          src={promo.imageUrl}
          alt={promo.name}
          style={{ width: '100%', height: 'auto', borderRadius: '4px', marginBottom: '8px' }}
        />
      )}
      <div style={{ fontWeight: 600, marginBottom: '4px' }}>{promo.name}</div>
      <div style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
        {promo.releaseYear}
      </div>
      {promo.rarity && (
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginTop: '4px' }}>
          {promo.rarity}
        </div>
      )}
    </Box>
  );
}
