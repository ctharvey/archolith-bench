import { useQuery } from '@tanstack/react-query';
import { fetchPromos } from '../api';
import { PageMain, PageTitle, Grid, EmptyState, SkeletonRow } from '@/ui';
import { PromoCardItem } from './PromoCardItem';

export function PromosPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['promos'],
    queryFn: fetchPromos,
  });

  if (isLoading) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <SkeletonRow count={6} />
      </PageMain>
    );
  }

  if (error || !data) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <EmptyState message="Failed to load promo cards." />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Promos ({data.totalCount})</PageTitle>
      <Grid cols={3} gap="md">
        {data.promos.map((promo) => (
          <PromoCardItem key={promo.id} promo={promo} />
        ))}
      </Grid>
    </PageMain>
  );
}
