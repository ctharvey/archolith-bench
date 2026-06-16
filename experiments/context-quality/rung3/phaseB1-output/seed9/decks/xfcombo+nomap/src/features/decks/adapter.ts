import { api } from '@/data/apiClient';
import type { DeckData, DecksPageData } from './types';

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  
  const decks: DeckData[] = result.data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Standard',
    totalValue: d.totalValue || 0,
    cardCount: d.cardCount || 0,
    topCards: (d.topCards || []).map((c: any) => ({
      name: c.name,
      price: c.price || 0,
      quantity: c.quantity || 1,
    })),
    updatedAt: d.updatedAt || '',
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;
  const avgValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return {
    decks,
    totalDecks,
    totalValue,
    avgValue,
  };
}
