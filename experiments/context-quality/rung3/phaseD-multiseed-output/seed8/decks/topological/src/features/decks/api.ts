import { api } from '@/data/apiClient';
import type { DeckDto } from './types';

/** Fetch all decks */
export async function fetchDecks(): Promise<DeckDto[]> {
  const res = await api.get('/decks');
  return res.json();
}
