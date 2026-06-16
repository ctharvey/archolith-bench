import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

function promoToColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `oklch(0.62 0.15 ${hue})`;
}

function promoToSym(name: string): string {
  const c = name.trim().charAt(0);
  if (/[A-Za-z0-9]/.test(c)) return c;
  return '◆';
}

export async function loadPromosData(signal?: AbortSignal): Promise<{
  promos: PromoCard[];
}> {
  const rows = await repo.market.matrix(100, signal);
  const promos: PromoCard[] = rows
    .filter(r => r.id.startsWith('promo-'))
    .map(r => ({
      id: r.id,
      name: r.name,
      year: r.releaseDate ? new Date(r.releaseDate).getFullYear() : 0,
      imageUrl: img(`/images/${r.id}/1.png`),
      color: promoToColor(r.id),
      sym: promoToSym(r.name),
    }));
  return { promos };
}
