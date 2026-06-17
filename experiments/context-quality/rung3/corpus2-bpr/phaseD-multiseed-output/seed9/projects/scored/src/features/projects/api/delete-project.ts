import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

export const deleteProject = ({ projectId }: { projectId: string }): Promise<void> => {
  return api.delete(`/projects/${projectId}`);
};

type UseDeleteProjectOptions = {
  mutationConfig?: MutationConfig<typeof deleteProject>;
};

export const useDeleteProject = ({ mutationConfig }: UseDeleteProjectOptions = {}) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};

  return useMutation({
    mutationFn: deleteProject,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({
        queryKey: ['projects'],
      });
      onSuccess?.(...args);
    },
    ...restConfig,
  });
};
