import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckData } from './types';

/** Load decks and compute derived data */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: DeckDto[] = result.data;

  const mappedDecks: DeckData[] = decks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Unknown',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    topCards: (d.topCards || []).map(c => ({
      name: c.name,
      price: c.price ?? 0,
    })),
    lastUpdated: d.lastUpdated ?? '',
  }));

  const totalDecks = mappedDecks.length;
  const totalValue = mappedDecks.reduce((sum, d) => sum + d.totalValue, 0);
  const avgDeckValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return {
    decks: mappedDecks,
    totalDecks,
    totalValue,
    avgDeckValue,
  };
}
