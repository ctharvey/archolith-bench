import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

export const markNotificationRead = ({
  notificationId,
}: {
  notificationId: string;
}): Promise<void> => {
  return api.patch(`/notifications/${notificationId}/read`);
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
