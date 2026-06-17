import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';
import { queryConfig } from '@/lib/react-query';
import { Tag } from '@/types/api';

type GetTagsOptions = {
  page?: number;
};

export const getTags = async ({ page = 1 }: GetTagsOptions = {}): Promise<{
  data: Tag[];
  meta: { page: number; totalPages: number };
}> => {
  const response = await apiClient.get('/tags', { params: { page } });
  return response.data;
};

export const getTagsQueryOptions = ({ page }: GetTagsOptions = {}) => ({
  queryKey: ['tags', { page }],
  queryFn: () => getTags({ page }),
});

export const useTags = ({ page }: GetTagsOptions = {}) => {
  return useQuery({
    ...getTagsQueryOptions({ page }),
    ...queryConfig,
  });
};
