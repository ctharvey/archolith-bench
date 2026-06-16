import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promos are identified by a special set prefix or category.
 */
export async function loadPromos(signal?: AbortSignal): Promise<PromoCard[]> {
  const rows = await repo.market.promos(signal);
  return rows.map(r => ({
    id: r.id,
    name: r.name,
    year: extractYear(r.releaseDate),
    imageUrl: r.imageUrl ? img(r.imageUrl) : null,
    rarity: r.rarity ?? 'Common',
    set: r.setName ?? 'Promo',
    number: r.number ?? '',
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
