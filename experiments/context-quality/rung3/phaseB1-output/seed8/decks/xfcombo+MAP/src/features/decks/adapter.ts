import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckData } from './types';

/** Load all decks and compute aggregate values */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: DeckData[] = result.data.map((dto: DeckDto) => ({
    id: dto.id,
    name: dto.name,
    format: dto.format,
    totalValue: dto.totalValue ?? 0,
    cardCount: dto.cardCount ?? 0,
    uniqueCards: dto.uniqueCards ?? 0,
    topCardName: dto.topCardName ?? '',
    topCardValue: dto.topCardValue ?? 0,
    lastUpdated: dto.lastUpdated ?? '',
  }));

  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const avgValue = totalDecks > 0 ? Math.round(totalValue / totalDecks) : 0;

  return { decks, totalDecks, totalValue, avgValue };
}
