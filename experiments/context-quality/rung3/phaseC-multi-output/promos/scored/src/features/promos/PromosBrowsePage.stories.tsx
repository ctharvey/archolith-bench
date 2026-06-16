import type { Meta, StoryObj } from '@storybook/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PromosBrowsePage } from './PromosBrowsePage';

const queryClient = new QueryClient();

const meta: Meta<typeof PromosBrowsePage> = {
  title: 'Features/Promos/PromosBrowsePage',
  component: PromosBrowsePage,
  decorators: [
    (Story) => (
      <QueryClientProvider client={queryClient}>
        <Story />
      </QueryClientProvider>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof PromosBrowsePage>;

export const Default: Story = {};
