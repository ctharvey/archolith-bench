import { api } from '@/data/apiClient';
import type { DeckDto, DecksPageData } from './types';

/** Fetch all decks from the API */
export async function fetchDecks(): Promise<DeckDto[]> {
  const response = await api.get<DeckDto[]>('/api/decks');
  return response.data;
}

/** Load decks page data */
export async function loadDecksData(): Promise<DecksPageData> {
  const decks = await fetchDecks();
  return {
    decks,
    totalDecks: decks.length,
  };
}
