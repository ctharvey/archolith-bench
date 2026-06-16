import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promos are identified by set IDs starting with "promo-".
 */
export async function loadPromos(signal?: AbortSignal): Promise<PromoCard[]> {
  const rows = await repo.market.matrix(100, signal);
  
  // Filter to promo sets only
  const promoRows = rows.filter(r => r.id.startsWith('promo-'));
  
  return promoRows.map(r => {
    // Extract year from release date (format: "2024-03-15" or "2024")
    const year = extractYear(r.releaseDate);
    
    return {
      id: r.id,
      name: r.name,
      year,
      imageUrl: r.topCardId ? img(`/images/${r.id}/${r.topCardId.split('-')[1]}.png`) : null,
      rarity: r.rarity ?? 'Common',
      set: r.serieName ?? '—',
      number: r.topCardId?.split('-')[1] ?? '—',
    };
  });
}

function extractYear(dateStr: string | null | undefined): number {
  if (!dateStr) return 0;
  const match = dateStr.match(/^(\d{4})/);
  return match ? parseInt(match[1], 10) : 0;
}
