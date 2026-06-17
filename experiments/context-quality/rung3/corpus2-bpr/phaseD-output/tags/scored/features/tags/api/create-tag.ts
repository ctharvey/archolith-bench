import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { apiClient } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';
import { Tag } from '@/types/api';

export const createTagInputSchema = z.object({
  label: z.string().min(1, 'Required'),
  color: z.string().min(1, 'Required'),
});

export type CreateTagInput = z.infer<typeof createTagInputSchema>;

export const createTag = async ({
  data,
}: {
  data: CreateTagInput;
}): Promise<{ data: Tag }> => {
  const response = await apiClient.post('/tags', data);
  return response.data;
};

type UseCreateTagOptions = {
  mutationConfig?: MutationConfig<typeof createTag>;
};

export const useCreateTag = ({ mutationConfig }: UseCreateTagOptions = {}) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};

  return useMutation({
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      onSuccess?.(...args);
    },
    ...restConfig,
    mutationFn: createTag,
  });
};
