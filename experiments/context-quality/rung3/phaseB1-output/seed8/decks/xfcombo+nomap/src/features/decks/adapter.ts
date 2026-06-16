import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, Deck } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: Deck[] = result.data.map((dto: DeckDto) => ({
    id: dto.id,
    name: dto.name,
    format: dto.format,
    totalValue: dto.totalValue,
    cardCount: dto.cardCount,
    topCards: dto.topCards || [],
    lastUpdated: dto.lastUpdated,
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;

  return { decks, totalValue, totalDecks };
}
