import React from 'react';
import { Box, Pill } from '@/ui';
import { formatUSD, pct } from '@/domain/formatters';
import { cardUrl } from '@/domain/slug';
import type { PromoCard } from './types';

interface PromoCardItemProps {
  promo: PromoCard;
}

export function PromoCardItem({ promo }: PromoCardItemProps) {
  const priceDisplay = promo.price != null ? formatUSD(promo.price) : '—';
  const d7Display = promo.d7 != null ? pct(promo.d7) : '—';
  const d30Display = promo.d30 != null ? pct(promo.d30) : '—';

  return (
    <Box>
      <a href={cardUrl(promo.id, promo.name)} className="block">
        {promo.imageUrl && (
          <img
            src={promo.imageUrl}
            alt={promo.name}
            className="w-full h-48 object-contain mb-2"
            loading="lazy"
          />
        )}
        <h3 className="text-sm font-semibold truncate">{promo.name}</h3>
        <div className="text-xs text-gray-500 mt-1">
          <span>{promo.releaseYear}</span>
          {promo.cardNumber && <span> · #{promo.cardNumber}</span>}
        </div>
        <div className="flex gap-2 mt-2">
          <Pill>{priceDisplay}</Pill>
          <Pill variant={promo.d7 != null && promo.d7 >= 0 ? 'up' : 'down'}>
            7d: {d7Display}
          </Pill>
          <Pill variant={promo.d30 != null && promo.d30 >= 0 ? 'up' : 'down'}>
            30d: {d30Display}
          </Pill>
        </div>
      </a>
    </Box>
  );
}
