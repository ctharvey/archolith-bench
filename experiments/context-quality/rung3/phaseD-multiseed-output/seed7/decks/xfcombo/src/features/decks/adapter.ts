import { api } from '@/data/apiClient';
import type { Deck, DecksPageData } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ signal });

  // The API returns decks with their market values already computed
  const decks: Deck[] = result.decks.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Standard',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    topCards: d.topCards || [],
    lastUpdated: d.lastUpdated || '',
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;

  return { decks, totalValue, totalDecks };
}
