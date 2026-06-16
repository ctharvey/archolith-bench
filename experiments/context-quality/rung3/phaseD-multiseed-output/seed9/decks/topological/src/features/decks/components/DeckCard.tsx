import type { DeckDto } from '../types';
import { formatUSD } from '@/domain/formatters';
import { Box, KpiCard } from '@/ui';

interface DeckCardProps {
  deck: DeckDto;
}

export function DeckCard({ deck }: DeckCardProps) {
  return (
    <Box className="deck-card">
      <h3 className="deck-card__name">{deck.name}</h3>
      <p className="deck-card__format">{deck.format}</p>
      <p className="deck-card__count">{deck.cardCount} cards</p>
      <KpiCard
        label="Total Market Value"
        value={formatUSD(deck.totalValue, { locale: true })}
      />
    </Box>
  );
}
