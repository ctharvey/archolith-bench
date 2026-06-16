import React from 'react';
import type { DeckDto } from '../types';
import { formatUSDshort } from '@/domain/formatters';
import { Box } from '@/ui/layout';

interface DeckCardProps {
  deck: DeckDto;
}

export const DeckCard: React.FC<DeckCardProps> = ({ deck }) => {
  return (
    <Box className="deck-card">
      <div className="deck-card__image">
        {deck.topCardImageUrl ? (
          <img src={deck.topCardImageUrl} alt={deck.topCardName ?? ''} />
        ) : (
          <div className="deck-card__placeholder">No Image</div>
        )}
      </div>
      <div className="deck-card__info">
        <h3 className="deck-card__name">{deck.name}</h3>
        <span className="deck-card__format">{deck.format}</span>
        <span className="deck-card__value">{formatUSDshort(deck.totalValue)}</span>
        <span className="deck-card__count">{deck.cardCount} cards</span>
      </div>
    </Box>
  );
};
