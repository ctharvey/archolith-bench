import type { PromoCard as PromoCardType } from '../types';
import { formatUSD, pct } from '@/domain/formatters';
import { cardUrl } from '@/domain/slug';
import { Spark } from '@/ui/charts';
import { KpiCard } from '@/ui/data-display';

interface PromoCardProps {
  promo: PromoCardType;
}

export function PromoCard({ promo }: PromoCardProps) {
  const sparkData = [promo.d7, promo.d30, promo.d90].filter((v): v is number => v !== null);
  
  return (
    <a
      href={cardUrl(promo.id, promo.name)}
      className="group block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
    >
      <div className="flex items-start gap-4">
        {/* Image */}
        <div className="h-24 w-18 flex-shrink-0 overflow-hidden rounded bg-gray-100 dark:bg-gray-700">
          {promo.imageUrl ? (
            <img
              src={promo.imageUrl}
              alt={promo.name}
              className="h-full w-full object-contain"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-gray-400">
              <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-blue-600 dark:text-gray-100 dark:group-hover:text-blue-400">
            {promo.name}
          </h3>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {promo.releaseYear} · {promo.source}
          </p>

          {/* Price & deltas */}
          <div className="mt-2 flex items-center gap-3">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {promo.fmv !== null ? formatUSD(promo.fmv) : '—'}
            </span>
            {promo.d7 !== null && (
              <span className={`text-xs font-medium ${promo.d7 >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {pct(promo.d7)}
              </span>
            )}
          </div>

          {/* Sparkline */}
          {sparkData.length >= 2 && (
            <div className="mt-1 h-6 w-20">
              <Spark data={sparkData} />
            </div>
          )}
        </div>
      </div>
    </a>
  );
}
