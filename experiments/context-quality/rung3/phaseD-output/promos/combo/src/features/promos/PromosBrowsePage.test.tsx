import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { PromosBrowsePage } from './PromosBrowsePage';
import { apiClient } from '@/lib/api-client';
import { vi } from 'vitest';

vi.mock('@/lib/api-client');

const mockCards = [
  {
    core: {
      id: 'promo-1',
      name: 'Pikachu (SWSH Promo)',
      image: '/images/pikachu.png',
      url: '/cards/promo-1',
      setId: 'swsh-promos',
      setName: 'SWSH Promos',
      rarity: 'Promo',
      number: 'SWSH001',
      types: ['Lightning'],
      variants: ['Normal'],
    },
    price: {
      marketPrice: 5.99,
      marketPriceUrl: null,
      primaryPrinting: 'Normal',
      delta7d: 0.5,
      delta30d: 1.2,
      rawDelta7d: 0.5,
      rawDelta30d: 1.2,
      deltaReliability7d: 0.8,
      deltaReliability30d: 0.7,
      deltaStatus7d: 'up',
      deltaStatus30d: 'up',
      priceFetchedAt: '2024-01-15T00:00:00Z',
      printings: null,
    },
    detail: null,
    primaryColor: '#FFD700',
    secondaryColor: '#FFA500',
  },
];

describe('PromosBrowsePage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('renders loading state', () => {
    (apiClient.get as any).mockReturnValue(new Promise(() => {}));
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PromosBrowsePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(screen.getByText('Promos')).toBeInTheDocument();
  });

  it('renders error state', async () => {
    (apiClient.get as any).mockRejectedValue(new Error('Network error'));
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PromosBrowsePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByText('Network error')).toBeInTheDocument();
  });

  it('renders promo cards', async () => {
    (apiClient.get as any).mockResolvedValue({
      data: { cards: mockCards, total: 1 },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PromosBrowsePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByText('Pikachu (SWSH Promo)')).toBeInTheDocument();
  });

  it('renders year filter', async () => {
    (apiClient.get as any).mockResolvedValue({
      data: { cards: mockCards, total: 1 },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PromosBrowsePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByRole('combobox')).toBeInTheDocument();
  });
});
