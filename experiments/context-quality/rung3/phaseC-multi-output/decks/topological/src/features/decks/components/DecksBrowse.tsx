import React, { useEffect, useState } from 'react';
import { fetchDecks } from '../api';
import { mapDeck } from '../mappers';
import type { Deck, DecksPageData } from '../types';
import { DeckList } from './DeckList';
import { PageMain, PageTitle, KpiCard, KpiStrip } from '@/ui';
import { formatUSDshort } from '@/domain/formatters';

export const DecksBrowse: React.FC = () => {
  const [data, setData] = useState<DecksPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDecks()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message ?? 'Failed to load decks');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <PageMain>
        <PageTitle>Decks</PageTitle>
        <div className="error-message">{error}</div>
      </PageMain>
    );
  }

  const decks = data?.decks ?? [];

  return (
    <PageMain>
      <PageTitle>Decks</PageTitle>
      <KpiStrip>
        <KpiCard
          label="Total Decks"
          value={data?.totalDecks ?? 0}
        />
        <KpiCard
          label="Total Market Value"
          value={data ? formatUSDshort(data.totalValue) : '—'}
        />
      </KpiStrip>
      <DeckList decks={decks} loading={loading} />
    </PageMain>
  );
};
