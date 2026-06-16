import type { DeckSummary } from './types';
import { formatUSDshort } from '@/domain/formatters';

/** Map a DeckSummary to display-ready props */
export function mapDeckToDisplay(deck: DeckSummary) {
  return {
    ...deck,
    totalValueDisplay: formatUSDshort(deck.totalValue),
    cardCountDisplay: `${deck.cardCount} cards`,
    uniqueCardsDisplay: `${deck.uniqueCards} unique`,
    updatedAtDisplay: deck.updatedAt
      ? new Date(deck.updatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      : '—',
  };
}
