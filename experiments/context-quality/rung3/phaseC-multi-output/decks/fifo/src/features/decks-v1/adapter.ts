import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { DeckV1 } from './types';

function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(deckId + '-') ? cardId.slice(deckId.length + 1) : cardId;
  return img(`/images/${deckId}/${number}.png`);
}

export async function loadDecksV1Data(signal?: AbortSignal): Promise<{
  decks: DeckV1[];
  totalValue: number;
}> {
  const rows = await repo.market.decks(100, signal);
  const decks: DeckV1[] = rows.map((r: any) => ({
    id: r.id,
    name: r.name,
    format: r.format ?? 'Standard',
    archetype: r.archetype ?? 'Unknown',
    totalValue: r.totalValue ?? 0,
    totalValueFormatted: formatCurrency(r.totalValue ?? 0),
    cardCount: r.cardCount ?? 0,
    uniqueCards: r.uniqueCards ?? 0,
    topCardName: r.topCardName ?? '',
    topCardValue: r.topCardValue ?? 0,
    topCardImageUrl: topCardImageUrl(r.id, r.topCardId),
    color: deckToColor(r.id),
    updatedAt: r.updatedAt ?? new Date().toISOString(),
  }));
  const totalValue = decks.reduce((a, d) => a + d.totalValue, 0);
  return { decks, totalValue };
}
