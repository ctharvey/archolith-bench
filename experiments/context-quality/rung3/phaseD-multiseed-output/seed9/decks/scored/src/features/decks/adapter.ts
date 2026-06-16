import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckSummary } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  const decks: DeckSummary[] = result.data.map((d: DeckDto) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Unknown',
    totalValue: d.totalValue || 0,
    cardCount: d.cardCount || 0,
    topCards: d.topCards?.slice(0, 3) || [],
    lastUpdated: d.lastUpdated || '',
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;
  const avgDeckValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return { decks, totalDecks, totalValue, avgDeckValue };
}
