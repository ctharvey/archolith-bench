import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../lib/api-client';
import { CardDto } from '../../../data/api-types';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { ErrorMessage } from '../../components/ErrorMessage';
import { CardGrid } from '../../components/CardGrid';
import { PageHeader } from '../../components/PageHeader';

interface PromoCard extends CardDto {
  releaseYear: number | null;
}

export const PromosBrowsePage: React.FC = () => {
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
        setPromos(response.data);
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
    <div className="promos-browse-page">
      <PageHeader
        title="Promo Cards"
        subtitle="Browse all promotional Pokémon cards"
      />
      <CardGrid
        cards={promos}
        onCardClick={handleCardClick}
        renderMetadata={(card: PromoCard) => (
          <div className="card-metadata">
            {card.releaseYear && (
              <span className="release-year">{card.releaseYear}</span>
            )}
            {card.core.rarity && (
              <span className="rarity">{card.core.rarity}</span>
            )}
          </div>
        )}
      />
    </div>
  );
};
