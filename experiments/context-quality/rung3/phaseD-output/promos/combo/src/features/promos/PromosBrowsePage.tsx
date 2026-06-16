import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { CardDto } from '@/data/api-types';
import { PageLayout } from '@/components/layout/PageLayout';
import { CardGrid } from '@/components/cards/CardGrid';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useSearchParams } from 'react-router-dom';
import { Pagination } from '@/components/ui/Pagination';
import { YearFilter } from '@/components/filters/YearFilter';

const PAGE_SIZE = 48;

export function PromosBrowsePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentPage = Number(searchParams.get('page') ?? '1');
  const yearFilter = searchParams.get('year') ?? undefined;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['promos', 'browse', { page: currentPage, year: yearFilter }],
    queryFn: () =>
      apiClient
        .get('/api/pokemon/cards/promos', {
          params: {
            page: currentPage,
            pageSize: PAGE_SIZE,
            year: yearFilter,
          },
        })
        .then((res) => res.data as { cards: CardDto[]; total: number }),
  });

  const totalPages = useMemo(
    () => (data ? Math.ceil(data.total / PAGE_SIZE) : 0),
    [data]
  );

  const handlePageChange = (page: number) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('page', String(page));
      return next;
    });
  };

  const handleYearChange = (year: string | undefined) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (year) {
        next.set('year', year);
      } else {
        next.delete('year');
      }
      next.set('page', '1');
      return next;
    });
  };

  if (isLoading) {
    return (
      <PageLayout title="Promos">
        <LoadingSpinner />
      </PageLayout>
    );
  }

  if (isError) {
    return (
      <PageLayout title="Promos">
        <ErrorMessage message={(error as Error)?.message ?? 'Failed to load promos'} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Promos">
      <div className="mb-6">
        <YearFilter value={yearFilter} onChange={handleYearChange} />
      </div>
      <CardGrid cards={data?.cards ?? []} />
      {totalPages > 1 && (
        <div className="mt-8 flex justify-center">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={handlePageChange}
          />
        </div>
      )}
    </PageLayout>
  );
}
