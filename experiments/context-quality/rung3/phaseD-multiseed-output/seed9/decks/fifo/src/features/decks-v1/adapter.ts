import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { DecksV1Deck } from './types';

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

/** First character of deck name as a symbol */
function deckToSym(name: string): string {
  const c = name.trim().charAt(0);
  if (/[A-Za-z0-9]/.test(c)) return c;
  return '◆';
}

/** Format a number as currency */
function formatCurrency(value: number): string {
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}k`;
  }
  return `$${value.toFixed(2)}`;
}

/**
 * Build DecksV1Deck[] from raw deck data.
 * Uses the same pattern as set-v3 adapter.
 */
export function buildV1Decks(rawDecks: Array<{
  id: string;
  name: string;
  format: string;
  archetype: string;
  totalValue: number;
  cardCount: number;
  uniqueCards: number;
  topCardId: string | null;
  updatedAt: string;
}>): DecksV1Deck[] {
  return rawDecks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format,
    archetype: d.archetype,
    totalValue: d.totalValue,
    totalValueFormatted: formatCurrency(d.totalValue),
    cardCount: d.cardCount,
    uniqueCards: d.uniqueCards,
    topCardId: d.topCardId,
    color: deckToColor(d.id),
    sym: deckToSym(d.name),
    updatedAt: d.updatedAt,
    topCardImageUrl: topCardImageUrl(d.id, d.topCardId),
  }));
}

/**
 * Parse a cardId like "sv08-208" into an image URL.
 * Card images live at /images/{setId}/{number}.png.
 */
function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  // Card ID is "{setId}-{number}"; strip the setId prefix to get the number.
  const setId = cardId.split('-')[0];
  const number = cardId.startsWith(setId + '-') ? cardId.slice(setId.length + 1) : cardId;
  return img(`/images/${setId}/${number}.png`);
}

/** Load all data needed by v1 Decks page */
export async function loadV1DecksData(signal?: AbortSignal): Promise<{
  decks: DecksV1Deck[];
  totalValue: number;
}> {
  const rawDecks = await repo.market.decks(100, signal);
  const decks = buildV1Decks(rawDecks);
  const totalValue = decks.reduce((a, d) => a + d.totalValue, 0);
  return { decks, totalValue };
}
