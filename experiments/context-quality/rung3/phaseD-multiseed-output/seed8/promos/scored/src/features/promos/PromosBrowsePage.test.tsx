import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PromosBrowsePage } from './PromosBrowsePage';
import { apiClient } from '../../lib/apiClient';

jest.mock('../../lib/apiClient');

const mockPromos = [
  {
    core: {
      id: 'promo-1',
      name: 'Pikachu (Promo)',
      image: '/images/pikachu-promo.png',
      url: '/cards/promo-1',
      setId: 'promo-set',
      setName: 'Promo Set',
      rarity: 'Rare',
      number: '001',
      types: ['Electric'],
      variants: ['Normal'],
    },
    price: null,
    detail: null,
    primaryColor: '#FFD700',
    secondaryColor: '#FFA500',
    releaseYear: 2023,
  },
  {
    core: {
      id: 'promo-2',
      name: 'Charizard (Promo)',
      image: '/images/charizard-promo.png',
      url: '/cards/promo-2',
      setId: 'promo-set',
      setName: 'Promo Set',
      rarity: 'Ultra Rare',
      number: '002',
      types: ['Fire'],
      variants: ['Normal'],
    },
    price: null,
    detail: null,
    primaryColor: '#FF4500',
    secondaryColor: '#FF6347',
    releaseYear: 2022,
  },
];

describe('PromosBrowsePage', () => {
  beforeEach(() => {
    (apiClient.get as jest.Mock).mockResolvedValue({ data: mockPromos });
  });

  it('renders loading state initially', () => {
    render(
      <BrowserRouter>
        <PromosBrowsePage />
      </BrowserRouter>
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders promo cards after loading', async () => {
    render(
      <BrowserRouter>
        <PromosBrowsePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Pikachu (Promo)')).toBeInTheDocument();
      expect(screen.getByText('Charizard (Promo)')).toBeInTheDocument();
    });
  });

  it('displays release years', async () => {
    render(
      <BrowserRouter>
        <PromosBrowsePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('2023')).toBeInTheDocument();
      expect(screen.getByText('2022')).toBeInTheDocument();
    });
  });

  it('handles API error', async () => {
    (apiClient.get as jest.Mock).mockRejectedValue(new Error('API Error'));

    render(
      <BrowserRouter>
        <PromosBrowsePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Failed to load promo cards')).toBeInTheDocument();
    });
  });
});
