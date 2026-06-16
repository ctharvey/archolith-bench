import { api } from '@/data/apiClient';
import type { DeckItem } from './types';
import { formatUSD } from '@/domain/formatters';
import { img } from '@/domain/img-url';

function idToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function nameSym(name: string): string {
  const match = name.match(/['"]?([A-Za-z])/);
  return match ? match[1].toUpperCase() : '#';
}

function deltaDir(n: number | null): 'up' | 'dn' | 'flat' {
  if (n == null) return 'flat';
  if (n > 0) return 'up';
  if (n < 0) return 'dn';
  return 'flat';
}

export async function loadDecksData(signal?: AbortSignal): Promise<{
  decks: DeckItem[];
  totalDecks: number;
  totalValue: number;
}> {
  const dtos = await api.getDecks(signal);

  const decks: DeckItem[] = dtos.map(d => ({
    id: d.id,
    name: d.name,
    format: d.format,
    cardCount: d.cardCount,
    totalValue: d.totalValue,
    displayValue: formatUSD(d.totalValue, { locale: true }),
    d7Pct: d.d7Pct != null ? `${d.d7Pct >= 0 ? '+' : ''}${d.d7Pct.toFixed(1)}%` : '—',
    d7Num: d.d7Pct ?? 0,
    d7Dir: deltaDir(d.d7Pct),
    sym: nameSym(d.name),
    color: idToColor(d.id),
    topCardImages: d.topCardImages.map(url => url ? img(url) : null),
    topCardIds: d.topCardIds,
    setNames: d.setNames,
  }));

  const totalValue = decks.reduce((a, d) => a + d.totalValue, 0);

  decks.sort((a, b) => b.totalValue - a.totalValue);

  return { decks, totalDecks: decks.length, totalValue };
}
