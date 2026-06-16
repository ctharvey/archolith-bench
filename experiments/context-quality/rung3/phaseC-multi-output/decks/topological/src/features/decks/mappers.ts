import type { Deck } from './types';
import { formatUSD } from '@/domain/formatters';

/** Map a raw deck DTO to a Deck domain model */
export function mapDeck(raw: any): Deck {
  return {
    id: raw.id ?? '',
    name: raw.name ?? 'Unknown Deck',
    format: raw.format ?? 'Unknown',
    totalValue: raw.totalValue ?? 0,
    cardCount: raw.cardCount ?? 0,
    uniqueCards: raw.uniqueCards ?? 0,
    topCardName: raw.topCardName ?? null,
    topCardImageUrl: raw.topCardImageUrl ?? null,
    updatedAt: raw.updatedAt ?? null,
    createdAt: raw.createdAt ?? null,
  };
}

/** Format deck total value for display */
export function formatDeckValue(value: number): string {
  return formatUSD(value, { locale: true });
}
