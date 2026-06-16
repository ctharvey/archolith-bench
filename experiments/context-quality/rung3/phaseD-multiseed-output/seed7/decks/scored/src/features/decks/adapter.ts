import { api } from '@/data/apiClient';
import type { DeckSummaryDto } from '@/data/apiClient';
import type { DecksPageData, DeckSummary } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 50 }, signal);
  const decks: DeckSummary[] = result.data.map((d: DeckSummaryDto) => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    topCards: (d.topCards ?? []).slice(0, 3).map(c => ({
      name: c.name,
      price: c.price ?? 0,
    })),
    lastUpdated: d.lastUpdated ?? '',
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;

  return {
    decks,
    totalDecks,
    totalValue,
    avgDeckValue: totalDecks > 0 ? totalValue / totalDecks : 0,
  };
}
