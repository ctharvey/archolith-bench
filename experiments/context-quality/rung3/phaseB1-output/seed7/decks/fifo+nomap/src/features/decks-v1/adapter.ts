import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { DeckV1, DecksV1Data } from './types';

/** Derive a stable color from deck id (OKLCH hue range) */
function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

/** Format a number as currency */
function formatCurrency(value: number): string {
  if (value >= 1000) {
    return '$' + (value / 1000).toFixed(1) + 'k';
  }
  return '$' + value.toFixed(2);
}

/** Parse a cardId like "sv08-208" into an image URL */
function topCardImageUrl(cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const parts = cardId.split('-');
  if (parts.length < 2) return null;
  const setId = parts[0];
  const number = parts.slice(1).join('-');
  return img(`/images/${setId}/${number}.png`);
}

/**
 * Build DeckV1[] from raw deck data from the repository.
 * The repository is expected to return decks with fields:
 * id, name, format, archetype, totalValue, cardCount, uniqueCards,
 * topCardId, topCardName, topCardValue, updatedAt
 */
export function buildV1Decks(rawDecks: any[]): DeckV1[] {
  return rawDecks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Standard',
    archetype: d.archetype ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    totalValueFormatted: formatCurrency(d.totalValue ?? 0),
    cardCount: d.cardCount ?? 0,
    uniqueCards: d.uniqueCards ?? 0,
    topCardId: d.topCardId ?? null,
    topCardName: d.topCardName ?? null,
    topCardValue: d.topCardValue ?? null,
    topCardImageUrl: topCardImageUrl(d.topCardId),
    updatedAt: d.updatedAt ?? '—',
    color: deckToColor(d.id),
  }));
}

/** Load all data needed by v1 Decks page */
export async function loadV1DecksData(signal?: AbortSignal): Promise<DecksV1Data> {
  const rawDecks = await repo.market.decks(100, signal);
  const decks = buildV1Decks(rawDecks);
  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const avgValue = totalDecks > 0 ? totalValue / totalDecks : 0;
  return { decks, totalDecks, totalValue, avgValue };
}
