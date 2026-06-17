import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

type DeleteTagOptions = {
  tagId: string;
};

export const deleteTag = async ({ tagId }: DeleteTagOptions): Promise<void> => {
  await apiClient.delete(`/tags/${tagId}`);
};

type UseDeleteTagOptions = {
  mutationConfig?: MutationConfig<typeof deleteTag>;
};

export const useDeleteTag = ({ mutationConfig }: UseDeleteTagOptions = {}) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};

  return useMutation({
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      onSuccess?.(...args);
    },
    ...restConfig,
    mutationFn: deleteTag,
  });
};
