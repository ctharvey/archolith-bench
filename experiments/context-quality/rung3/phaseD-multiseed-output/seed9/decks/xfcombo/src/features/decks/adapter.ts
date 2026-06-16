import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckItem } from './types';

/** Load decks data from API and compute derived values */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: DeckDto[] = result.data;

  const items: DeckItem[] = decks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format,
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    updatedAt: d.updatedAt ?? '',
  }));

  const totalDecks = items.length;
  const totalValue = items.reduce((sum, d) => sum + d.totalValue, 0);
  const avgValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return {
    decks: items,
    totalDecks,
    totalValue,
    avgValue,
  };
}
