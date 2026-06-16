import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CardDto } from '../../data/api-types';
import { apiClient } from '../../lib/api-client';
import { CardGrid } from '../../components/card/CardGrid';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { ErrorMessage } from '../../components/ui/ErrorMessage';
import { PageHeader } from '../../components/layout/PageHeader';

interface PromoCard extends CardDto {
  releaseYear: number | null;
}

export const PromosBrowseScreen: React.FC = () => {
  const navigate = useNavigate();
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPromos = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<PromoCard[]>('/api/pokemon/cards/promos');
        setPromos(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load promo cards');
      } finally {
        setLoading(false);
      }
    };

    fetchPromos();
  }, []);

  const handleCardClick = (cardId: string) => {
    navigate(`/cards/${cardId}`);
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="promos-browse-screen">
      <PageHeader
        title="Promo Cards"
        subtitle={`${promos.length} promo cards`}
      />
      <CardGrid
        cards={promos}
        onCardClick={handleCardClick}
        renderExtraInfo={(card: PromoCard) => (
          <span className="promo-release-year">
            {card.releaseYear ? `Released ${card.releaseYear}` : 'Year unknown'}
          </span>
        )}
      />
    </div>
  );
};
