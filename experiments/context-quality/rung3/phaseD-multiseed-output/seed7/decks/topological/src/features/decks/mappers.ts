import type { DeckSummary } from './types';
import { formatUSD } from '@/domain/formatters';

/** Map a DeckSummary to display-friendly shape */
export function mapDeckToDisplay(deck: DeckSummary) {
  return {
    ...deck,
    totalValueDisplay: formatUSD(deck.totalValue, { locale: true }),
    cardCountDisplay: `${deck.cardCount} cards`,
    uniqueCardsDisplay: `${deck.uniqueCards} unique`,
    updatedAtDisplay: deck.updatedAt
      ? new Date(deck.updatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      : '—',
  };
}

export type DeckDisplay = ReturnType<typeof mapDeckToDisplay>;
