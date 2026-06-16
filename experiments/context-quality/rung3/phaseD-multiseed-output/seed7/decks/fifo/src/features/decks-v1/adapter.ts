import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { DeckV1, DecksV1Data } from './types';

function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function formatValue(value: number): string {
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}k`;
  }
  return `$${value.toFixed(2)}`;
}

function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(deckId + '-') ? cardId.slice(deckId.length + 1) : cardId;
  return img(`/images/${deckId}/${number}.png`);
}

export async function loadDecksV1Data(signal?: AbortSignal): Promise<DecksV1Data> {
  const decks = await repo.market.decks(100, signal);
  const mapped: DeckV1[] = decks.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Standard',
    archetype: d.archetype ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    totalValueFormatted: formatValue(d.totalValue ?? 0),
    cardCount: d.cardCount ?? 0,
    uniqueCards: d.uniqueCards ?? 0,
    topCardId: d.topCardId ?? null,
    topCardImageUrl: topCardImageUrl(d.id, d.topCardId),
    color: deckToColor(d.id),
    updatedAt: d.updatedAt ?? '—',
  }));
  const totalValue = mapped.reduce((sum, d) => sum + d.totalValue, 0);
  return { decks: mapped, totalDecks: mapped.length, totalValue };
}
