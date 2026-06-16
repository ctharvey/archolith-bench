import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { MatrixRow } from '@/domain/models';
import type { Deck, DecksBrowseData } from './types';

function deckToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function parseCellVal(v: string): number {
  const n = parseFloat(v.replace(/[+%$,]/g, ''));
  return isNaN(n) ? 0 : n;
}

function buildDecks(rows: MatrixRow[]): Deck[] {
  return rows.map(r => {
    const totalValue = r.cells[0]?.value ?? '0';
    const cardCount = r.cells[1]?.value ?? '0';
    const uniqueCards = r.cells[2]?.value ?? '0';
    const topCardValue = r.cells[3]?.value ?? '0';
    const topCardName = r.cells[4]?.value ?? '—';
    const format = r.cells[5]?.value ?? 'Standard';

    const totalValueNum = parseCellVal(totalValue);
    const topCardValueNum = parseCellVal(topCardValue);

    return {
      id: r.id,
      name: r.name,
      format,
      totalValue: totalValueNum,
      totalValueFormatted: formatCurrency(totalValueNum),
      cardCount: parseInt(cardCount, 10) || 0,
      uniqueCards: parseInt(uniqueCards, 10) || 0,
      topCardName,
      topCardValue: topCardValueNum,
      topCardImageUrl: r.topCardId ? img(`/images/cards/${r.topCardId}.png`) : null,
      color: deckToColor(r.id),
      lastUpdated: r.releaseDate ?? '—',
    };
  });
}

export async function loadDecksBrowseData(signal?: AbortSignal): Promise<DecksBrowseData> {
  const rows = await repo.market.matrix(100, signal);
  const decks = buildDecks(rows);
  const totalDecks = decks.length;
  const totalValue = decks.reduce((sum, d) => sum + d.totalValue, 0);
  return { decks, totalDecks, totalValue };
}
