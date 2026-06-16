import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

/**
 * Load all promo cards from the repository.
 * Promo cards are identified by having a "promo" tag or set prefix.
 */
export async function loadPromos(signal?: AbortSignal): Promise<PromoCard[]> {
  const rows = await repo.market.matrix(100, signal);
  
  // Filter for promo cards (those with "promo" in their id or name)
  const promoRows = rows.filter(r => 
    r.id.toLowerCase().includes('promo') || 
    r.name.toLowerCase().includes('promo') ||
    r.serieName?.toLowerCase().includes('promo')
  );

  return promoRows.map(r => ({
    id: r.id,
    name: r.name,
    year: extractYear(r.releaseDate),
    imageUrl: buildPromoImageUrl(r.id, r.topCardId),
    rarity: r.rarity || 'Common',
    set: r.serieName || '—',
    number: r.topCardId?.split('-')[1] || '—',
  }));
}

function extractYear(releaseDate: string | null | undefined): number {
  if (!releaseDate) return 0;
  const year = parseInt(releaseDate.split('-')[0], 10);
  return isNaN(year) ? 0 : year;
}

function buildPromoImageUrl(setId: string, cardId: string | null | undefined): string | null {
  if (!cardId) return null;
  const number = cardId.startsWith(setId + '-') ? cardId.slice(setId.length + 1) : cardId;
  return img(`/images/${setId}/${number}.png`);
}
