import { api } from '@/data/apiClient';
import type { DecksPageData, Deck } from './types';

const FORMAT_COLORS: Record<string, string> = {
  Standard: '#0654ba',
  Expanded: '#e63946',
  Legacy: '#2a9d8f',
  Unlimited: '#d4943a',
};

function formatColor(format: string): string {
  return FORMAT_COLORS[format] ?? '#888';
}

export async function loadDecksData(signal?: AbortSignal): Promise<DecksPageData> {
  const result = await api.getDecks({}, signal);
  const decks: Deck[] = result.data.map((d: any) => ({
    id: d.id,
    name: d.name,
    format: d.format ?? 'Unknown',
    totalValue: d.totalValue ?? 0,
    cardCount: d.cardCount ?? 0,
    lastUpdated: d.lastUpdated ?? '',
    color: formatColor(d.format ?? 'Unknown'),
  }));

  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  const avgValue = totalDecks > 0 ? totalValue / totalDecks : 0;

  return { decks, totalDecks, totalValue, avgValue };
}
