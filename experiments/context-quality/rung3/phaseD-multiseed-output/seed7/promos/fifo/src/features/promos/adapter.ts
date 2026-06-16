import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promo cards are identified by having a "promo" tag in their metadata.
 */
export async function loadPromos(signal?: AbortSignal): Promise<PromoCard[]> {
  const cards = await repo.market.promos(signal);
  return cards.map(card => ({
    id: card.id,
    name: card.name,
    year: extractYear(card.releaseDate),
    imageUrl: card.imageUrl ? img(card.imageUrl) : null,
    rarity: card.rarity ?? 'Common',
    set: card.setName ?? 'Promo',
    number: card.number ?? '—',
  }));
}

/**
 * Extract the year from a date string like "2024-03-15" or "2024".
 */
function extractYear(dateStr: string | null | undefined): number {
  if (!dateStr) return 0;
  const match = dateStr.match(/^(\d{4})/);
  return match ? parseInt(match[1], 10) : 0;
}
