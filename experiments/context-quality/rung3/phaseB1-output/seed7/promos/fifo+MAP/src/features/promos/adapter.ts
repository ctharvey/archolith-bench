import { repo } from '@/data/repository';
import { img } from '@/domain/img-url';
import type { PromoCard } from './types';

export async function loadPromosData(signal?: AbortSignal): Promise<PromoCard[]> {
  const cards = await repo.cards.promos(signal);
  return cards.map(c => ({
    id: c.id,
    name: c.name,
    year: c.releaseYear ?? 0,
    imageUrl: c.imageUrl ? img(c.imageUrl) : null,
    rarity: c.rarity ?? '—',
    set: c.setName ?? '—',
    number: c.cardNumber ?? '—',
  }));
}
