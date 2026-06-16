import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PromosBrowsePage } from './PromosBrowsePage';
import { apiClient } from '@/lib/api-client';

jest.mock('@/lib/api-client');

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

const mockPromosResponse = {
  cards: [
    {
      core: {
        id: 'promo-1',
        name: 'Pikachu (2023)',
        image: '/images/pikachu.png',
        url: '/cards/promo-1',
        setId: 'swsh-promos',
        setName: 'SWSH Black Star Promos',
        rarity: 'Promo',
        number: '2023-001',
        types: ['Lightning'],
        variants: ['Normal'],
      },
      price: {
        marketPrice: 5.99,
        marketPriceUrl: null,
        primaryPrinting: null,
        delta7d: null,
        delta30d: null,
        rawDelta7d: null,
        rawDelta30d: null,
        deltaReliability7d: null,
        deltaReliability30d: null,
        deltaStatus7d: null,
        deltaStatus30d: null,
        priceFetchedAt: null,
        printings: null,
      },
      detail: null,
      primaryColor: null,
      secondaryColor: null,
    },
    {
      core: {
        id: 'promo-2',
        name: 'Charizard (2022)',
        image: '/images/charizard.png',
        url: '/cards/promo-2',
        setId: 'swsh-promos',
        setName: 'SWSH Black Star Promos',
        rarity: 'Promo',
        number: '2022-001',
        types: ['Fire'],
        variants: ['Normal'],
      },
      price: {
        marketPrice: 25.00,
        marketPriceUrl: null,
        primaryPrinting: null,
        delta7d: null,
        delta30d: null,
        rawDelta7d: null,
        rawDelta30d: null,
        deltaReliability7d: null,
        deltaReliability30d: null,
        deltaStatus7d: null,
        deltaStatus30d: null,
        deltaStatus7d: null,
        deltaStatus30d: null,
        priceFetchedAt: null,
        printings: null,
      },
      detail: null,
      primaryColor: null,
      secondaryColor: null,
    },
  ],
  total: 2,
};

describe('PromosBrowsePage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    jest.clearAllMocks();
  });

  const renderPage = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <PromosBrowsePage />
      </QueryClientProvider>
    );
  };

  it('shows loading state initially', () => {
    mockApiClient.get.mockResolvedValueOnce(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows error state on failure', async () => {
    mockApiClient.get.mockRejectedValueOnce(new Error('Network error'));
    renderPage();
    expect(await screen.findByText(/failed to load promos/i)).toBeInTheDocument();
  });

  it('shows empty state when no promos', async () => {
    mockApiClient.get.mockResolvedValueOnce({ data: { cards: [], total: 0 } });
    renderPage();
    expect(await screen.findByText(/no promo cards found/i)).toBeInTheDocument();
  });

  it('renders promos grouped by year', async () => {
    mockApiClient.get.mockResolvedValueOnce({ data: mockPromosResponse });
    renderPage();

    expect(await screen.findByText('2023')).toBeInTheDocument();
    expect(screen.getByText('2022')).toBeInTheDocument();
    expect(screen.getByText('Pikachu (2023)')).toBeInTheDocument();
    expect(screen.getByText('Charizard (2022)')).toBeInTheDocument();
  });

  it('renders page header', async () => {
    mockApiClient.get.mockResolvedValueOnce({ data: mockPromosResponse });
    renderPage();

    expect(await screen.findByText('Promos')).toBeInTheDocument();
    expect(screen.getByText('Browse promotional Pokémon cards')).toBeInTheDocument();
  });
});
