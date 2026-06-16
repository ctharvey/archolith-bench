import React from 'react';
import { Box, KpiCard } from '@/ui';
import { cardUrl } from '@/domain/slug';
import type { DeckSummary } from '../types';
import { mapDeckToDisplay } from '../mappers';

interface DeckCardProps {
  deck: DeckSummary;
}

export const DeckCard: React.FC<DeckCardProps> = ({ deck }) => {
  const display = mapDeckToDisplay(deck);

  return (
    <Box className="deck-card">
      <a href={`/deck/${deck.id}`} className="deck-card__link">
        <div className="deck-card__image">
          {deck.topCardImageUrl ? (
            <img src={deck.topCardImageUrl} alt={deck.topCardName ?? ''} />
          ) : (
            <div className="deck-card__placeholder">No image</div>
          )}
        </div>
        <div className="deck-card__info">
          <h3 className="deck-card__name">{deck.name}</h3>
          <p className="deck-card__format">{deck.format}</p>
          <KpiCard label="Market Value" value={display.totalValueDisplay} />
          <div className="deck-card__stats">
            <span>{display.cardCountDisplay}</span>
            <span>{display.uniqueCardsDisplay}</span>
          </div>
          <p className="deck-card__updated">Updated {display.updatedAtDisplay}</p>
        </div>
      </a>
    </Box>
  );
};
