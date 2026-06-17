import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

export const markNotificationReadInputSchema = z.object({
  notificationId: z.string(),
});

export type MarkNotificationReadInput = z.infer<typeof markNotificationReadInputSchema>;

export const markNotificationRead = ({
  data,
}: {
  data: MarkNotificationReadInput;
}): Promise<void> => {
  return api.patch(`/notifications/${data.notificationId}/read`);
};

type UseMarkNotificationReadOptions = {
  mutationConfig?: MutationConfig<typeof markNotificationRead>;
};

export const useMarkNotificationRead = ({
  mutationConfig,
}: UseMarkNotificationReadOptions = {}) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};

  return useMutation({
    onSuccess: (...args) => {
      queryClient.invalidateQueries({
        queryKey: ['notifications'],
      });
      onSuccess?.(...args);
    },
    ...restConfig,
    mutationFn: markNotificationRead,
  });
};
