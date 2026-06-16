import React, { useEffect, useState } from 'react';
import { PageMain, PageTitle, Grid, EmptyState, SkeletonRow } from '@/ui';
import { fetchDecks } from '../api';
import type { DecksPageData } from '../types';
import { DeckCard } from './DeckCard';
import { formatUSDshort } from '@/domain/formatters';

export const DecksBrowseScreen: React.FC = () => {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDecks()
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
        <SkeletonRow count={6} />
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
      <PageTitle>
        Decks
        <span className="page-title__sub">
          {data.totalDecks} decks · Total value {formatUSDshort(data.totalValue)}
        </span>
      </PageTitle>
      <Grid columns={3} gap="md">
        {data.decks.map((deck) => (
          <DeckCard key={deck.id} deck={deck} />
        ))}
      </Grid>
    </PageMain>
  );
};
