import React from 'react';
import type { Deck } from '../types';
import { formatDeckValue } from '../mappers';
import { formatDate } from '@/domain/formatters';
import { Box } from '@/ui/layout';

interface DeckCardProps {
  deck: Deck;
}

export const DeckCard: React.FC<DeckCardProps> = ({ deck }) => {
  return (
    <Box className="deck-card">
      <div className="deck-card__header">
        {deck.topCardImageUrl && (
          <img
            src={deck.topCardImageUrl}
            alt={deck.topCardName ?? ''}
            className="deck-card__image"
          />
        )}
        <div className="deck-card__info">
          <h3 className="deck-card__name">{deck.name}</h3>
          <span className="deck-card__format">{deck.format}</span>
        </div>
      </div>
      <div className="deck-card__stats">
        <div className="deck-card__stat">
          <span className="deck-card__stat-label">Total Value</span>
          <span className="deck-card__stat-value">{formatDeckValue(deck.totalValue)}</span>
        </div>
        <div className="deck-card__stat">
          <span className="deck-card__stat-label">Cards</span>
          <span className="deck-card__stat-value">{deck.cardCount}</span>
        </div>
        <div className="deck-card__stat">
          <span className="deck-card__stat-label">Unique</span>
          <span className="deck-card__stat-value">{deck.uniqueCards}</span>
        </div>
      </div>
      {deck.updatedAt && (
        <div className="deck-card__updated">
          Updated {formatDate(deck.updatedAt)}
        </div>
      )}
    </Box>
  );
};
