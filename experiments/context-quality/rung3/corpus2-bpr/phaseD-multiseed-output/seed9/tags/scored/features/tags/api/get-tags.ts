import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';
import { queryConfig } from '@/lib/react-query';

type GetTagsParams = {
  page?: number;
};

export const getTags = ({ page = 1 }: GetTagsParams = {}): Promise<{
  data: Array<{
    id: string;
    label: string;
    color: string;
  }>;
  meta: {
    page: number;
    totalPages: number;
  };
}> => {
  return apiClient.get(`/tags?page=${page}`);
};

export const getTagsQueryOptions = ({ page }: GetTagsParams = {}) => ({
  queryKey: ['tags', { page }],
  queryFn: () => getTags({ page }),
});

export const useTags = ({ page }: GetTagsParams = {}) => {
  return useQuery({
    ...getTagsQueryOptions({ page }),
    ...queryConfig,
  });
};
