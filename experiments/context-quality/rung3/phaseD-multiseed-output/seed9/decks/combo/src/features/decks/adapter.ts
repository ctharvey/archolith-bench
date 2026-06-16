import { api } from '@/data/apiClient';
import type { DecksPageData, Deck } from './types';

const FORMAT_COLORS: Record<string, string> = {
  Standard: '#0654ba',
  Expanded: '#e63946',
  Unlimited: '#2a9d8f',
  Gym: '#d4943a',
};

function formatColor(format: string): string {
  return FORMAT_COLORS[format] ?? '#888';
}

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 50 }, signal);
  const decks: Deck[] = result.data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format || 'Unknown',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    uniqueCards: d.uniqueCards ?? 0,
    lastUpdated: d.lastUpdated ?? '',
    color: formatColor(d.format || 'Unknown'),
  }));

  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const totalDecks = decks.length;
  const avgDeckValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return { decks, totalDecks, totalValue, avgDeckValue };
}
