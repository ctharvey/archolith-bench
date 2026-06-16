import React, { useEffect, useState } from 'react';
import { PageMain, PageTitle, Grid, EmptyState, SkeletonRow } from '@/ui';
import { PromoCard } from './types';
import { fetchPromos } from './api';
import { PromoCardItem } from './PromoCardItem';

export function PromosPage() {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchPromos()
      .then((data) => {
        if (!cancelled) {
          setPromos(data.promos);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load promos');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
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
        <EmptyState message={error} />
      </PageMain>
    );
  }

  if (promos.length === 0) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <EmptyState message="No promo cards found." />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Promos</PageTitle>
      <Grid>
        {promos.map((promo) => (
          <PromoCardItem key={promo.id} promo={promo} />
        ))}
      </Grid>
    </PageMain>
  );
}
