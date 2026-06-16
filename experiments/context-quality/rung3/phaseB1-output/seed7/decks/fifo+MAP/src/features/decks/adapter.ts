import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Deck, DecksBrowseData } from './types';

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

export async function loadDecksBrowseData(signal?: AbortSignal): Promise<DecksBrowseData> {
  const decksData = await repo.decks.list(signal);
  
  const decks: Deck[] = decksData.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Standard',
    totalValue: d.totalValue || 0,
    totalValueFormatted: formatCurrency(d.totalValue || 0),
    cardCount: d.cardCount || 0,
    uniqueCards: d.uniqueCards || 0,
    topCardName: d.topCardName || '',
    topCardValue: d.topCardValue || 0,
    topCardImageUrl: d.topCardId ? img(`/images/cards/${d.topCardId}.png`) : null,
    color: deckToColor(d.id),
    lastUpdated: d.lastUpdated || new Date().toISOString(),
  }));

  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);

  return { decks, totalDecks, totalValue };
}
