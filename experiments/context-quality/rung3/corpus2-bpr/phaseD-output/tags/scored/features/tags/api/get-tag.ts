import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';
import { queryConfig } from '@/lib/react-query';
import { Tag } from '@/types/api';

type GetTagOptions = {
  tagId: string;
};

export const getTag = async ({ tagId }: GetTagOptions): Promise<{ data: Tag }> => {
  const response = await apiClient.get(`/tags/${tagId}`);
  return response.data;
};

export const getTagQueryOptions = (tagId: string) => ({
  queryKey: ['tags', tagId],
  queryFn: () => getTag({ tagId }),
});

export const useTag = ({ tagId }: GetTagOptions) => {
  return useQuery({
    ...getTagQueryOptions(tagId),
    ...queryConfig,
  });
};
