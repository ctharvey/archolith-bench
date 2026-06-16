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

export function buildDecks(data: any[]): DeckV1[] {
  return data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Standard',
    archetype: d.archetype ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    totalValueFormatted: formatCurrency(d.totalValue ?? 0),
    cardCount: d.cardCount ?? 0,
    uniqueCards: d.uniqueCards ?? 0,
    topCardName: d.topCardName ?? '',
    topCardValue: d.topCardValue ?? 0,
    topCardImageUrl: d.topCardId ? img(`/images/${d.topCardId.replace('-', '/')}.png`) : null,
    color: deckToColor(d.id),
    lastUpdated: d.lastUpdated ?? '—',
  }));
}

export async function loadDecksData(signal?: AbortSignal): Promise<{
  decks: DeckV1[];
  totalDecks: number;
  totalMarketValue: number;
}> {
  const data = await repo.market.decks(100, signal);
  const decks = buildDecks(data);
  const totalMarketValue = decks.reduce((a, d) => a + d.totalValue, 0);
  return { decks, totalDecks: decks.length, totalMarketValue };
}
