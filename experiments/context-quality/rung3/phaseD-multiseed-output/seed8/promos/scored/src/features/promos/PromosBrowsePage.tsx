import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../lib/apiClient';
import { CardDto } from '../../data/api-types';
import { CardGrid } from '../../components/CardGrid';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { ErrorMessage } from '../../components/ErrorMessage';
import { PageHeader } from '../../components/PageHeader';

interface PromoCard extends CardDto {
  releaseYear?: number;
}

export const PromosBrowsePage: React.FC = () => {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchPromos = async () => {
      try {
        setLoading(true);
        setError(null);
        // Fetch promo cards from the API
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
      <div className="promos-browse-page__content">
        <CardGrid
          cards={promos}
          onCardClick={handleCardClick}
          renderCardMeta={(card: PromoCard) => (
            <div className="card-meta">
              {card.releaseYear && (
                <span className="card-meta__year">{card.releaseYear}</span>
              )}
              {card.core?.rarity && (
                <span className="card-meta__rarity">{card.core.rarity}</span>
              )}
            </div>
          )}
        />
      </div>
    </div>
  );
};
