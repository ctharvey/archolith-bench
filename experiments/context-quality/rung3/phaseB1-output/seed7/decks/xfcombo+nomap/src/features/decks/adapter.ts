import { api } from '@/data/apiClient';
import type { Deck, DecksPageData } from './types';

/** Load all decks and compute aggregate values */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const decks: Deck[] = await api.getDecks({}, signal);

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;

  return { decks, totalValue, totalDecks };
}
