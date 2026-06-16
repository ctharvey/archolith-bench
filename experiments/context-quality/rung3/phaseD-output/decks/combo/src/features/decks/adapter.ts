import { api } from '@/data/apiClient';
import type { DeckDto, DecksPageData } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  const decks: DeckDto[] = result.data ?? [];
  
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  
  return {
    decks,
    totalDecks: decks.length,
    totalValue,
  };
}
