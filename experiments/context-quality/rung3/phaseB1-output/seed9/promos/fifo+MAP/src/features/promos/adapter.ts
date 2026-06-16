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

export async function loadPromosData(signal?: AbortSignal): Promise<PromoCard[]> {
  const promos = await repo.promos.list(signal);
  return promos.map(p => ({
    id: p.id,
    name: p.name,
    year: p.year,
    imageUrl: p.imageUrl ? img(p.imageUrl) : null,
    color: promoToColor(p.id),
    sym: promoToSym(p.name),
  }));
}
