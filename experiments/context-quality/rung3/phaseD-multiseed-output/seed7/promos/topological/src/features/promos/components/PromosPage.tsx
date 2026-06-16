import { usePromise } from '@/hooks/usePromise';
import { fetchPromos } from '../api';
import { PromoGrid } from './PromoGrid';
import { PageMain, PageTitle, SkeletonRow } from '@/ui';

export function PromosPage() {
  const { data, loading, error } = usePromise(() => fetchPromos(), []);

  return (
    <PageMain>
      <PageTitle>Promos</PageTitle>
      {loading && (
        <div class="space-y-4">
          <SkeletonRow count={6} />
        </div>
      )}
      {error && (
        <div class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load promos. Please try again later.
        </div>
      )}
      {data && <PromoGrid promos={data.promos} />}
    </PageMain>
  );
}
