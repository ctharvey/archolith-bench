import type { PromoCard } from '../types';
import { formatUSD } from '@/domain/formatters';
import { cardUrl } from '@/domain/slug';

interface PromoCardProps {
  promo: PromoCard;
}

export function PromoCard({ promo }: PromoCardProps) {
  const href = cardUrl(promo.id, promo.name);

  return (
    <a
      href={href}
      class="group block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
    >
      <div class="aspect-square overflow-hidden rounded-md bg-gray-100 dark:bg-gray-700">
        {promo.imageUrl ? (
          <img
            src={promo.imageUrl}
            alt={promo.name}
            class="h-full w-full object-contain transition-transform group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div class="flex h-full items-center justify-center text-gray-400">
            <svg class="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
      </div>
      <div class="mt-3">
        <h3 class="text-sm font-medium text-gray-900 truncate dark:text-gray-100">
          {promo.name}
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {promo.releaseYear} · {promo.source}
        </p>
        <div class="mt-2 flex items-center justify-between">
          <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {promo.price != null ? formatUSD(promo.price) : '—'}
          </span>
          {promo.d7 != null && (
            <span class={`text-xs font-medium ${promo.d7 >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {promo.d7 >= 0 ? '+' : ''}{promo.d7.toFixed(1)}%
            </span>
          )}
        </div>
      </div>
    </a>
  );
}
