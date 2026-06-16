import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../../api/apiClient';
import { CardDto } from '../../data/api-types';
import { useAuth } from '../../hooks/useAuth';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { ErrorMessage } from '../../components/ui/ErrorMessage';
import { CardGrid } from '../../components/cards/CardGrid';
import { PageHeader } from '../../components/layout/PageHeader';

interface PromoCard extends CardDto {
  releaseYear: number | null;
}

const PromosBrowsePage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [promos, setPromos] = useState<PromoCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPromos = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiGet<PromoCard[]>('/api/pokemon/cards/promos');
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
    <div className="promos-browse-page">
      <PageHeader
        title="Promo Cards"
        subtitle={`${promos.length} promo cards available`}
      />
      <div className="promos-filters">
        <select
          className="promos-year-filter"
          onChange={(e) => {
            const year = e.target.value;
            if (year === 'all') {
              setPromos(promos);
            } else {
              setPromos(promos.filter((p) => p.releaseYear?.toString() === year));
            }
          }}
        >
          <option value="all">All Years</option>
          {Array.from(new Set(promos.map((p) => p.releaseYear).filter(Boolean)))
            .sort((a, b) => b! - a!)
            .map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
        </select>
      </div>
      <CardGrid
        cards={promos.map((promo) => ({
          id: promo.core.id,
          name: promo.core.name,
          image: promo.core.image,
          price: promo.price?.marketPrice ?? null,
          subtitle: promo.releaseYear ? `Released ${promo.releaseYear}` : null,
        }))}
        onCardClick={handleCardClick}
        emptyMessage="No promo cards found"
      />
    </div>
  );
};

export default PromosBrowsePage;
