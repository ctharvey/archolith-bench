import { api } from '@/data/apiClient';
import type { DeckDto } from '@/data/apiClient';
import type { DecksPageData, DeckSummary } from './types';

/** Load all decks and compute aggregate values */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: DeckDto[] = result.data;

  const deckSummaries: DeckSummary[] = decks.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format,
    totalCards: d.totalCards,
    marketValue: d.marketValue ?? 0,
    topCardName: d.topCardName ?? '',
    topCardValue: d.topCardValue ?? 0,
    updatedAt: d.updatedAt ?? '',
  }));

  const totalDecks = deckSummaries.length;
  const totalValue = deckSummaries.reduce((sum, d) => sum + d.marketValue, 0);
  const avgValue = totalDecks > 0 ? Math.round(totalValue / totalDecks) : 0;

  return {
    decks: deckSummaries,
    totalDecks,
    totalValue,
    avgValue,
  };
}
