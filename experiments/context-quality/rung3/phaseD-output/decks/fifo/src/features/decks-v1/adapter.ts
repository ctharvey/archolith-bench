import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { DeckV1 } from './types';

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

/** Parse a cardId like "sv08-208" into an image URL */
function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(deckId + '-') ? cardId.slice(deckId.length + 1) : cardId;
  return img(`/images/${deckId}/${number}.png`);
}

/**
 * Build DeckV1[] from raw deck data.
 * Assumes repo.decks.list() returns an array of deck objects with:
 * id, name, format, archetype, totalValue, cardCount, uniqueCards, topCardId, updatedAt, winRate, tier
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
    topCardImageUrl: topCardImageUrl(d.id, d.topCardId),
    color: deckToColor(d.id),
    updatedAt: d.updatedAt ?? '—',
    winRate: d.winRate ?? null,
    tier: d.tier ?? null,
  }));
}

/** Load all decks data */
export async function loadV1DecksData(signal?: AbortSignal): Promise<{
  decks: DeckV1[];
  totalValue: number;
}> {
  const rawDecks = await repo.decks.list(signal);
  const decks = buildV1Decks(rawDecks);
  const totalValue = decks.reduce((a, d) => a + d.totalValue, 0);
  return { decks, totalValue };
}
