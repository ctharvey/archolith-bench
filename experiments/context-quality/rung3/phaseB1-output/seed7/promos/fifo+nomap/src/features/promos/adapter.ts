import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promos are identified by set IDs starting with "promo" or "smp".
 */
export async function loadPromos(signal?: AbortSignal): Promise<PromoCard[]> {
  const rows = await repo.market.matrix(200, signal);
  
  const promoRows = rows.filter(r => {
    const id = r.id.toLowerCase();
    return id.startsWith('promo') || id.startsWith('smp');
  });

  return promoRows.map(r => {
    const year = extractYear(r.releaseDate);
    return {
      id: r.id,
      name: r.name,
      year,
      imageUrl: img(`/images/${r.id}/${r.topCardId?.split('-')[1] || '1'}.png`),
      rarity: r.rarity || 'Common',
      set: r.serieName || '—',
      number: r.topCardId?.split('-')[1] || '—',
    };
  });
}

function extractYear(dateStr: string | null | undefined): number {
  if (!dateStr) return 0;
  const match = dateStr.match(/\d{4}/);
  return match ? parseInt(match[0], 10) : 0;
}
