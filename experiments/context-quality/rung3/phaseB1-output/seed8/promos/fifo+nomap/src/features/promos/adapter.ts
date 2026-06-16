import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

function parseYear(releaseDate: string | null | undefined): number {
  if (!releaseDate) return 0;
  const year = parseInt(releaseDate.slice(0, 4), 10);
  return isNaN(year) ? 0 : year;
}

function promoImageUrl(cardId: string): string | null {
  // Promo images follow pattern /images/promos/{cardId}.png
  return img(`/images/promos/${cardId}.png`);
}

export async function loadPromosData(signal?: AbortSignal): Promise<{
  promos: PromoCard[];
  totalPromos: number;
}> {
  // Assuming there's a method to fetch promo cards from the repository
  // This would need to be implemented based on actual data source
  const rows = await repo.market.promos(100, signal);
  const promos = rows.map(r => ({
    id: r.id,
    name: r.name,
    year: parseYear(r.releaseDate),
    imageUrl: promoImageUrl(r.id),
    rarity: r.rarity ?? '—',
    set: r.setName ?? '—',
    number: r.number ?? '—',
  }));
  const totalPromos = promos.length;
  return { promos, totalPromos };
}
