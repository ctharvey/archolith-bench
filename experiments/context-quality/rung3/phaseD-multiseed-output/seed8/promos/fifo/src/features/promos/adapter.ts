import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promos are identified by having a "promo" tag or being in a promo set.
 */
export async function loadPromosData(signal?: AbortSignal): Promise<{
  promos: PromoCard[];
  years: number[];
}> {
  const rows = await repo.market.matrix(100, signal);
  
  // Filter for promo cards (those with "promo" in their id or name)
  const promoRows = rows.filter(r => 
    r.id.toLowerCase().includes('promo') || 
    r.name.toLowerCase().includes('promo') ||
    r.serieName?.toLowerCase().includes('promo')
  );

  const promos: PromoCard[] = promoRows.map(r => {
    // Extract year from release date
    const year = r.releaseDate ? new Date(r.releaseDate).getFullYear() : 0;
    
    return {
      id: r.id,
      name: r.name,
      year,
      imageUrl: r.topCardId ? img(`/images/${r.id}/${r.topCardId.split('-')[1]}.png`) : null,
      rarity: r.rarity || 'Common',
      set: r.serieName || '—',
      number: r.topCardId?.split('-')[1] || '—',
    };
  });

  // Get unique years sorted descending
  const years = [...new Set(promos.map(p => p.year))].filter(y => y > 0).sort((a, b) => b - a);

  return { promos, years };
}
