import { repo } from '@/data/repository';
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
    return `$${(value / 1000).toFixed(1)}k`;
  }
  return `$${value.toFixed(2)}`;
}

/**
 * Build DeckV1[] from raw deck data.
 * Assumes repo.decks.list() returns an array of deck objects with:
 *   id, name, format, archetype, totalValue, cardCount, uniqueCards, topCardId, topCardName, updatedAt
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
    color: deckToColor(d.id),
    updatedAt: d.updatedAt ?? '—',
  }));
}

/** Load all data needed by Decks v1 page */
export async function loadV1DecksData(signal?: AbortSignal): Promise<DecksV1Data> {
  const rawDecks = await repo.decks.list(signal);
  const decks = buildV1Decks(rawDecks);
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  return { decks, totalDecks: decks.length, totalValue };
}
