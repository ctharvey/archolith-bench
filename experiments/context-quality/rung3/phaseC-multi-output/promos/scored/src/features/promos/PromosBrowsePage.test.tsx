import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PromosBrowsePage } from './PromosBrowsePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <PromosBrowsePage />
    </QueryClientProvider>
  );
}

describe('PromosBrowsePage', () => {
  it('renders the page header', () => {
    renderWithProviders();
    expect(screen.getByText('Promo Cards')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    renderWithProviders();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
