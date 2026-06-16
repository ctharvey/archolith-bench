import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { CardDto } from '@/data/api-types';
import { CardGrid } from '@/features/cards/CardGrid';
import { PageHeader } from '@/components/PageHeader';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorMessage } from '@/components/ErrorMessage';
import { EmptyState } from '@/components/EmptyState';
import { YearFilter } from '@/features/promos/YearFilter';

interface PromosResponse {
  cards: CardDto[];
  total: number;
}

async function fetchPromos(year?: number): Promise<PromosResponse> {
  const params = new URLSearchParams();
  if (year) params.set('year', String(year));
  return apiClient.get(`/api/pokemon/cards/promos?${params.toString()}`);
}

export function PromosBrowsePage() {
  const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined);

  const { data, isLoading, isError, error } = useQuery<PromosResponse>({
    queryKey: ['promos', selectedYear],
    queryFn: () => fetchPromos(selectedYear),
  });

  const years = useMemo(() => {
    if (!data?.cards) return [];
    const yearSet = new Set<number>();
    data.cards.forEach((card) => {
      const releaseDate = card.core?.releaseDate;
      if (releaseDate) {
        const year = new Date(releaseDate).getFullYear();
        if (!isNaN(year)) yearSet.add(year);
      }
    });
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Promo Cards"
        description="Browse all promotional Pokémon cards"
      />

      <YearFilter
        years={years}
        selectedYear={selectedYear}
        onYearChange={setSelectedYear}
      />

      {isLoading && <LoadingSpinner />}

      {isError && (
        <ErrorMessage
          message={error instanceof Error ? error.message : 'Failed to load promos'}
        />
      )}

      {data && data.cards.length === 0 && (
        <EmptyState message="No promo cards found" />
      )}

      {data && data.cards.length > 0 && (
        <CardGrid cards={data.cards} />
      )}
    </div>
  );
}
