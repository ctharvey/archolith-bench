import { api } from '@/data/apiClient';
import type { DecksPageData } from './types';

/** Fetch all decks for the browse screen */
export async function fetchDecks(): Promise<DecksPageData> {
  const response = await api.get('/decks');
  const data = await response.json();
  return {
    decks: data.decks ?? [],
    totalDecks: data.totalDecks ?? 0,
    totalValue: data.totalValue ?? 0,
  };
}
