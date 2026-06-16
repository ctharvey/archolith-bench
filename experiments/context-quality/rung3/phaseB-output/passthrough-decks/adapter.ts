import { repo } from '@/data/repository';
import { usdCompact, pct, deltaDir } from '@/domain/formatters';
import type { DeckItem } from './types';

function setToColor(setName: string): string {
  let hash = 0;
  for (let i = 0; i < setName.length; i++) {
    hash = ((hash << 5) - hash) + setName.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function parseUsdCompact(s: string): number | null {
  if (s === '—') return null;
  const num = parseFloat(s.replace(/[$,]/g, ''));
  if (s.includes('k')) return num * 1000;
  if (s.includes('M')) return num * 1_000_000;
  return num;
}

function parsePct(s: string): number | null {
  if (!s || s === '—') return null;
  return parseFloat(s.replace(/[+%]/g, ''));
}

export async function loadDecksData(signal?: AbortSignal): Promise<{
  decks: DeckItem[];
  totalDecks: number;
  totalMarketValue: number;
  avgDeckValue: number;
  biggestDeck: string | null;
}> {
  const rows = await repo.market.matrix(100, signal);

  const items: DeckItem[] = [];

  for (const r of rows) {
    if (r.count <= 0) continue;

    const avgFmv = parseUsdCompact(r.cells[3]?.value ?? '—');
    if (avgFmv == null) continue;

    const totalValue = avgFmv * r.count;
    const deltaNum = parsePct(r.cells[0]?.value ?? null);

    items.push({
      setId: r.id,
      setName: r.name,
      serieName: r.serieName,
      cardCount: r.count,
      avgFmv,
      totalValue,
      totalValueStr: usdCompact(totalValue),
      avgValueStr: usdCompact(avgFmv),
      delta7d: deltaNum,
      delta7dStr: deltaNum != null ? pct(deltaNum) : '—',
      delta7dDir: deltaDir(deltaNum),
      topCardId: r.topCardId ?? null,
      releaseDate: r.releaseDate ?? null,
      color: setToColor(r.name),
    });
  }

  items.sort((a, b) => (b.totalValue ?? 0) - (a.totalValue ?? 0));

  const totalMarketValue = items.reduce((s, d) => s + (d.totalValue ?? 0), 0);

  return {
    decks: items,
    totalDecks: items.length,
    totalMarketValue,
    avgDeckValue: items.length > 0 ? totalMarketValue / items.length : 0,
    biggestDeck: items[0]?.setName ?? null,
  };
}
