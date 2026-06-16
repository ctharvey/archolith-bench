import { api } from '@/data/apiClient';
import type { DeckBrowseDto } from '@/data/apiClient';
import type { DecksPageData, DeckBrowseItem } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  const decks: DeckBrowseItem[] = result.data.map((d: DeckBrowseDto) => ({
    id: d.id,
    name: d.name,
    format: d.format,
    totalValue: d.totalValue,
    cardCount: d.cardCount,
    updatedAt: d.updatedAt,
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);

  return {
    decks,
    totalValue,
    totalDecks: decks.length,
  };
}
