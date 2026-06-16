import type { DeckDto } from './types';
import { formatUSDshort } from '@/domain/formatters';

/** Map a DeckDto to display-friendly shape */
export function mapDeckForDisplay(deck: DeckDto): {
  id: string;
  name: string;
  format: string;
  totalValueLabel: string;
  cardCount: number;
  uniqueCards: number;
  topCardName: string | null;
  topCardImageUrl: string | null;
  updatedAt: string;
} {
  return {
    id: deck.id,
    name: deck.name,
    format: deck.format,
    totalValueLabel: formatUSDshort(deck.totalValue),
    cardCount: deck.cardCount,
    uniqueCards: deck.uniqueCards,
    topCardName: deck.topCardName,
    topCardImageUrl: deck.topCardImageUrl,
    updatedAt: deck.updatedAt,
  };
}
