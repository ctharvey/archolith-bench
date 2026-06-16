import React, { useEffect, useState } from 'react';
import { fetchDecksPageData } from '../api';
import type { DecksPageData } from '../types';
import { DeckList } from './DeckList';
import { PageMain, PageTitle, Box } from '@/ui/layout';
import { KpiCard, KpiStrip } from '@/ui/data-display';
import { Skeleton, EmptyState } from '@/ui/feedback';
import { formatUSDshort, compactCount } from '@/domain/formatters';

export const DecksBrowseScreen: React.FC = () => {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDecksPageData()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? 'Failed to load decks');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <Skeleton count={6} />
      </PageMain>
    );
  }

  if (error) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <EmptyState message={error} />
      </PageMain>
    );
  }

  if (!data || data.decks.length === 0) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <EmptyState message="No decks found." />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>Decks</PageTitle>
      <KpiStrip>
        <KpiCard label="Total Decks" value={compactCount(data.totalDecks)} />
        <KpiCard label="Total Value" value={formatUSDshort(data.totalValue)} />
      </KpiStrip>
      <DeckList decks={data.decks} />
    </PageMain>
  );
};
