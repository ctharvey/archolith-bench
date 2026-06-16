import { api } from '@/data/apiClient';
import type { DecksPageData, Deck } from './types';

const FORMAT_COLORS: Record<string, string> = {
  Standard: '#0654ba',
  Pioneer: '#e63946',
  Modern: '#2a9d8f',
  Legacy: '#d4943a',
  Vintage: '#9b59b6',
  Commander: '#e67e22',
  Pauper: '#1abc9c',
};

function formatColor(format: string): string {
  return FORMAT_COLORS[format] ?? '#95a5a6';
}

/** Load decks and compute derived views */
export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({ page: 0, size: 100 }, signal);
  const decks: Deck[] = result.data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format,
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    lastUpdated: d.lastUpdated ?? '',
    color: formatColor(d.format),
  }));

  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const avgDeckValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return { decks, totalDecks, totalValue, avgDeckValue };
}
