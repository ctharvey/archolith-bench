import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckSummary } from './types';

/** Load all decks and compute summary data */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  const decks: DeckDto[] = result.data;

  const summaries: DeckSummary[] = decks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    lastUpdated: d.lastUpdated ?? '',
    topCards: d.topCards?.slice(0, 3) ?? [],
  }));

  const totalValue = summaries.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = summaries.length;
  const avgDeckValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return {
    decks: summaries.sort((a, b) => b.totalValue - a.totalValue),
    totalDecks,
    totalValue,
    avgDeckValue,
  };
}
