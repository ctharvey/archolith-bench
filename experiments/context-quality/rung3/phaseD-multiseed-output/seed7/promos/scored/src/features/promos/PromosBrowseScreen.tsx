import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CardDto } from '../../data/api-types';
import { apiGet } from '../../utils/api';
import { useAuth } from '../../hooks/useAuth';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { ErrorMessage } from '../../components/ErrorMessage';
import { CardGrid } from '../../components/CardGrid';
import { PageHeader } from '../../components/PageHeader';

interface PromoCard extends CardDto {
  releaseYear: number | null;
}

export const PromosBrowseScreen: React.FC = () => {
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchPromos = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiGet<PromoCard[]>('/api/pokemon/cards/promos', token);
        setPromos(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load promo cards');
      } finally {
        setLoading(false);
      }
    };

    fetchPromos();
  }, [token]);

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
        subtitle="Browse all promotional Pokémon cards"
      />
      <div className="promos-browse-screen__content">
        <CardGrid
          cards={promos}
          onCardClick={handleCardClick}
          renderCardMeta={(card: PromoCard) => (
            <div className="promos-browse-screen__meta">
              {card.releaseYear && (
                <span className="promos-browse-screen__year">
                  {card.releaseYear}
                </span>
              )}
              {card.core?.rarity && (
                <span className="promos-browse-screen__rarity">
                  {card.core.rarity}
                </span>
              )}
            </div>
          )}
        />
      </div>
    </div>
  );
};
