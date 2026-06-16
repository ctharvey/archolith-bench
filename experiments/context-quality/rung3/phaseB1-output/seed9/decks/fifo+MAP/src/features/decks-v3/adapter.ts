import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { MatrixRow } from '@/domain/models';
import type { DecksV3Deck } from './types';

function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function deckToSym(name: string): string {
  const c = name.trim().charAt(0);
  if (/[A-Za-z0-9]/.test(c)) return c;
  return '◆';
}

function parseValue(v: string): number {
  const n = parseFloat(v.replace(/[+%$,]/g, ''));
  return isNaN(n) ? 0 : n;
}

export function buildV3Decks(rows: MatrixRow[]): DecksV3Deck[] {
  return rows.map(r => {
    const totalValue = r.cells[0]?.value ?? '$0';
    const topCardValue = r.cells[1]?.value ?? '$0';
    const cardCount = r.cells[2]?.value ?? '0';
    const uniqueCards = r.cells[3]?.value ?? '0';
    const format = r.cells[4]?.value ?? 'Standard';
    const lastUpdated = r.cells[5]?.value ?? '—';

    return {
      id: r.id,
      name: r.name,
      format,
      totalValue,
      totalValueNum: parseValue(totalValue),
      cardCount: parseInt(cardCount) || 0,
      uniqueCards: parseInt(uniqueCards) || 0,
      topCardName: r.topCardName ?? '—',
      topCardValue,
      color: deckToColor(r.id),
      sym: deckToSym(r.name),
      lastUpdated,
    };
  });
}

export async function loadV3DecksData(signal?: AbortSignal): Promise<{
  decks: DecksV3Deck[];
  totalDecks: number;
}> {
  const rows = await repo.market.decks(100, signal);
  const decks = buildV3Decks(rows);
  return { decks, totalDecks: decks.length };
}
