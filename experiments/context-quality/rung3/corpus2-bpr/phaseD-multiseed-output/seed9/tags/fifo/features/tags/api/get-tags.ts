import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Tag } from '@/types/api';

export const getTags = (): Promise<{ data: Tag[] }> => {
  return api.get('/tags');
};

export const getTagsQueryOptions = () => {
  return {
    queryKey: ['tags'],
    queryFn: getTags,
  };
};

type UseTagsOptions = {
  queryConfig?: QueryConfig<typeof getTags>;
};

export const useTags = ({ queryConfig }: UseTagsOptions = {}) => {
  return useQuery({
    ...getTagsQueryOptions(),
    ...queryConfig,
  });
};
