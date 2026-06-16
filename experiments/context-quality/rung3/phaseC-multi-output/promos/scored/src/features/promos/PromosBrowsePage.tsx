import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { CardDto } from '@/data/api-types';
import { CardGrid } from '@/features/cards/CardGrid';
import { PageHeader } from '@/components/PageHeader';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorMessage } from '@/components/ErrorMessage';

interface PromosResponse {
  cards: CardDto[];
  total: number;
}

async function fetchPromos(): Promise<PromosResponse> {
  const response = await apiClient.get<PromosResponse>('/api/pokemon/cards/promos');
  return response.data;
}

export function PromosBrowsePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['promos'],
    queryFn: fetchPromos,
  });

  const cardsWithYear = useMemo(() => {
    if (!data?.cards) return [];
    return data.cards.map((card) => {
      const year = card.core.setName?.match(/\b(20\d{2})\b/)?.[1] ?? null;
      return { ...card, releaseYear: year };
    });
  }, [data]);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message="Failed to load promo cards." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Promo Cards"
        description="Browse all promotional Pokémon cards, sorted by release year."
      />
      <CardGrid
        cards={cardsWithYear}
        renderMeta={(card) => {
          if ('releaseYear' in card && card.releaseYear) {
            return <span className="text-sm text-muted-foreground">{card.releaseYear as string}</span>;
          }
          return null;
        }}
      />
    </div>
  );
}
