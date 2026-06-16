import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { Deck } from './types';

function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function parseCellVal(v: string): number {
  const n = parseFloat(v.replace(/[+%$,]/g, ''));
  return isNaN(n) ? 0 : n;
}

function topCardImageUrl(deckId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(deckId + '-') ? cardId.slice(deckId.length + 1) : cardId;
  return img(`/images/${deckId}/${number}.png`);
}

export async function loadDecksData(signal?: AbortSignal): Promise<{
  decks: Deck[];
  totalValue: number;
}> {
  const rows = await repo.market.decks(100, signal);
  const decks: Deck[] = rows.map((r: any) => {
    const totalValue = r.cells[0]?.value ?? '$0';
    const winRate = r.cells[1]?.value ?? '—';
    const popularity = r.cells[2]?.value ?? '—';

    return {
      id: r.id,
      name: r.name,
      format: r.format ?? 'Standard',
      archetype: r.archetype ?? '—',
      totalValue,
      totalValueFormatted: totalValue,
      cardCount: r.count ?? 0,
      topCardId: r.topCardId ?? null,
      topCardImageUrl: topCardImageUrl(r.id, r.topCardId),
      color: deckToColor(r.id),
      released: r.releaseDate ?? '—',
      winRate,
      winRateNum: parseCellVal(winRate),
      popularity,
      popularityNum: parseCellVal(popularity),
    };
  });

  const totalValue = decks.reduce((sum, d) => sum + d.totalValueNum, 0);
  return { decks, totalValue };
}
