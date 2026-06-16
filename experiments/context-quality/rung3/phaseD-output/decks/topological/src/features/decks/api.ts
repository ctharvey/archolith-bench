import { api } from '@/data/apiClient';
import type { DeckSummary, DecksPageData } from './types';

/** Fetch all decks for the browse screen */
export async function fetchDecks(): Promise<DecksPageData> {
  const response = await api.get<DeckSummary[]>('/decks');
  const decks = response.data;
  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  return { decks, totalDecks, totalValue };
}
