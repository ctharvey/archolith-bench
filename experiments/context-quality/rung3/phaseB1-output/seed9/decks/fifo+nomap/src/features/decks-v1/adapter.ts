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

/** Parse a cardId like "sv08-208" into an image URL */
function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(deckId + '-') ? cardId.slice(deckId.length + 1) : cardId;
  return img(`/images/${deckId}/${number}.png`);
}

/** Load all decks data */
export async function loadDecksV1Data(signal?: AbortSignal): Promise<{
  decks: DeckV1[];
  totalValue: number;
}> {
  const rows = await repo.market.decks(100, signal);
  const decks: DeckV1[] = rows.map((r: any) => {
    const totalValue = r.totalValue ?? 0;
    return {
      id: r.id,
      name: r.name,
      format: r.format ?? '—',
      archetype: r.archetype ?? '—',
      totalValue,
      totalValueFormatted: formatCurrency(totalValue),
      cardCount: r.cardCount ?? 0,
      uniqueCards: r.uniqueCards ?? 0,
      topCardId: r.topCardId ?? null,
      topCardImageUrl: topCardImageUrl(r.id, r.topCardId),
      color: deckToColor(r.id),
      sym: deckToSym(r.name),
      released: r.releaseDate ?? '—',
      updatedAt: r.updatedAt ?? '—',
    };
  });
  const totalValue = decks.reduce((a, d) => a + d.totalValue, 0);
  return { decks, totalValue };
}
