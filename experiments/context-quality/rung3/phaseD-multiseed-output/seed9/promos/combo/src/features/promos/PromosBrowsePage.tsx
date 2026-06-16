import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { CardDto } from '@/data/api-types';
import { CardGrid } from '@/features/cards/CardGrid';
import { PageHeader } from '@/components/PageHeader';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorMessage } from '@/components/ErrorMessage';
import { EmptyState } from '@/components/EmptyState';

interface PromosResponse {
  cards: CardDto[];
  total: number;
}

async function fetchPromos(): Promise<PromosResponse> {
  const response = await apiClient.get<PromosResponse>('/api/pokemon/cards/promos');
  return response.data;
}

export function PromosBrowsePage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['promos'],
    queryFn: fetchPromos,
  });

  const promosByYear = useMemo(() => {
    if (!data?.cards) return new Map<number, CardDto[]>();
    
    const grouped = new Map<number, CardDto[]>();
    
    for (const card of data.cards) {
      const year = extractYear(card);
      if (!grouped.has(year)) {
        grouped.set(year, []);
      }
      grouped.get(year)!.push(card);
    }
    
    // Sort years descending
    const sorted = new Map<number, CardDto[]>();
    const years = Array.from(grouped.keys()).sort((a, b) => b - a);
    for (const year of years) {
      sorted.set(year, grouped.get(year)!);
    }
    
    return sorted;
  }, [data]);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (isError) {
    return <ErrorMessage message={error?.message ?? 'Failed to load promos'} />;
  }

  if (!data || data.cards.length === 0) {
    return (
      <>
        <PageHeader title="Promos" subtitle="Browse promotional Pokémon cards" />
        <EmptyState message="No promo cards found" />
      </>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Promos" subtitle="Browse promotional Pokémon cards" />
      
      {Array.from(promosByYear.entries()).map(([year, cards]) => (
        <section key={year}>
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
            {year}
          </h2>
          <CardGrid cards={cards} />
        </section>
      ))}
    </div>
  );
}

function extractYear(card: CardDto): number {
  // Try to extract year from release date or set name
  const releaseDate = card.core.setName;
  if (releaseDate) {
    const match = releaseDate.match(/\b(20\d{2})\b/);
    if (match) {
      return parseInt(match[1], 10);
    }
  }
  
  // Fallback: try to get year from card number prefix (common for promos like "2023 XY-P")
  const cardNumber = card.core.number;
  if (cardNumber) {
    const match = cardNumber.match(/^(20\d{2})/);
    if (match) {
      return parseInt(match[1], 10);
    }
  }
  
  return 0; // Unknown year
}
