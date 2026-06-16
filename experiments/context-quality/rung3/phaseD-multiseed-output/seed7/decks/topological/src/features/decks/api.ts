import { api } from '@/data/apiClient';
import type { DecksApiResponse, DeckSummary } from './types';

/** Fetch all decks from the API */
export async function fetchDecks(): Promise<DeckSummary[]> {
  const res = await api.get<DecksApiResponse>('/api/decks');
  return res.decks;
}
