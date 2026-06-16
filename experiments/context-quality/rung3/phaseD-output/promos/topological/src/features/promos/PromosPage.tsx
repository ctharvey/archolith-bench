import { useQuery } from '@tanstack/react-query';
import { fetchPromos } from './api';
import { PageMain, PageTitle, Grid, EmptyState, SkeletonRow } from '@/ui';
import { PromoCardItem } from './PromoCardItem';

export function PromosPage() {
  const { data: promos, isLoading, error } = useQuery({
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

  if (error) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <EmptyState message="Failed to load promo cards." />
      </PageMain>
    );
  }

  if (!promos || promos.length === 0) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <EmptyState message="No promo cards available." />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Promos</PageTitle>
      <Grid columns={3} gap="md">
        {promos.map((promo) => (
          <PromoCardItem key={promo.id} promo={promo} />
        ))}
      </Grid>
    </PageMain>
  );
}
