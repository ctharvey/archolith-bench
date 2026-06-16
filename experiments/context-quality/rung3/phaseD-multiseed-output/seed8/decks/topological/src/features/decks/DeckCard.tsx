import React from 'react';
import type { DeckDisplay } from './types';
import { Box } from '@/ui/layout';
import { KpiCard } from '@/ui/data-display';

interface DeckCardProps {
  deck: DeckDisplay;
}

export function DeckCard({ deck }: DeckCardProps) {
  return (
    <Box className="deck-card">
      <div className="deck-card__header">
        <h3 className="deck-card__name">{deck.name}</h3>
        <span className="deck-card__format">{deck.format}</span>
      </div>
      <div className="deck-card__stats">
        <KpiCard label="Market Value" value={deck.totalValueFormatted} />
        <KpiCard label="Cards" value={String(deck.cardCount)} />
      </div>
      <div className="deck-card__meta">
        <span>Updated {deck.updatedAtFormatted}</span>
      </div>
    </Box>
  );
}
