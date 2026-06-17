import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Meta, Project } from '@/types/api';

export const getProjects = ({
  page = 1,
}: {
  page?: number;
} = {}): Promise<{ data: Project[]; meta: Meta }> => {
  return api.get('/projects', {
    params: {
      page,
    },
  });
};

export const getProjectsQueryOptions = (page?: number) => {
  return queryOptions({
    queryKey: ['projects', page],
    queryFn: () => getProjects({ page }),
  });
};

type UseProjectsOptions = {
  page?: number;
  queryConfig?: QueryConfig<typeof getProjects>;
};

export const useProjects = ({ page, queryConfig }: UseProjectsOptions) => {
  return useQuery({
    ...getProjectsQueryOptions(page),
    ...queryConfig,
  });
};
