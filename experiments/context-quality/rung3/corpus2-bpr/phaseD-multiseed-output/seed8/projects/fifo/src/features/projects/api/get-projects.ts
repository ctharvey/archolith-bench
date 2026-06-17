import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Project } from '@/types/api';

export const getProjects = (): Promise<{ data: Project[] }> => {
  return api.get('/projects');
};

export const getProjectsQueryOptions = () => {
  return queryOptions({
    queryKey: ['projects'],
    queryFn: getProjects,
  });
};

type UseProjectsOptions = {
  queryConfig?: QueryConfig<typeof getProjects>;
};

export const useProjects = ({ queryConfig }: UseProjectsOptions = {}) => {
  return useQuery({
    ...getProjectsQueryOptions(),
    ...queryConfig,
  });
};
