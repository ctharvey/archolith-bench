import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';
import { Notification } from '@/types/api';

type MarkNotificationReadOptions = {
  notificationId: string;
};

export const markNotificationRead = ({
  notificationId,
}: MarkNotificationReadOptions): Promise<Notification> => {
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
    mutationFn: markNotificationRead,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({
        queryKey: ['notifications'],
      });
      onSuccess?.(...args);
    },
    ...restConfig,
  });
};
