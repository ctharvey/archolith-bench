import { api } from '@/data/apiClient';
import type { Deck } from './types';
import type { DecksPageData } from './types';

/** Load decks data from the API */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 50 }, signal);
  
  const decks: Deck[] = result.data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Unknown',
    totalCards: d.totalCards || 0,
    marketValue: d.marketValue || 0,
    topCards: d.topCards || [],
    lastUpdated: d.lastUpdated || '',
  }));

  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.marketValue, 0);

  return { decks, totalDecks, totalValue };
}
