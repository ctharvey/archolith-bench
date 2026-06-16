import type { PromoCard } from '../types';
import { Box } from '@/ui';
import { formatDate } from '@/domain/formatters';

interface PromoCardItemProps {
  promo: PromoCard;
}

export function PromoCardItem({ promo }: PromoCardItemProps) {
  return (
    <Box>
      {promo.imageUrl && (
        <img
          src={promo.imageUrl}
          alt={promo.name}
          style={{ width: '100%', height: 'auto', borderRadius: '8px' }}
        />
      )}
      <h3>{promo.name}</h3>
      <p>Released: {promo.releaseYear}</p>
      {promo.cardNumber && <p>Card #{promo.cardNumber}</p>}
      <p>Series: {promo.series}</p>
    </Box>
  );
}
