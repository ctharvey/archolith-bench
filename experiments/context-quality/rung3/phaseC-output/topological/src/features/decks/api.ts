import { api } from '@/data/apiClient';
import type { DeckDto, DecksPageData } from './types';

/** Fetch all decks from the API */
export async function fetchDecks(): Promise<DeckDto[]> {
  return api.get<DeckDto[]>('/decks');
}

/** Fetch decks page data (decks + aggregates) */
export async function fetchDecksPageData(): Promise<DecksPageData> {
  const decks = await fetchDecks();
  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  return { decks, totalDecks, totalValue };
}
