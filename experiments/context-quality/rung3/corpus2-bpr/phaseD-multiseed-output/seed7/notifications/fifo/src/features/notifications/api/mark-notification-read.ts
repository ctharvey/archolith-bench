import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

import { getNotificationsQueryOptions } from './get-notifications';

export const markNotificationRead = ({ notificationId }: { notificationId: string }) => {
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
        queryKey: getNotificationsQueryOptions().queryKey,
      });
      onSuccess?.(...args);
    },
    ...restConfig,
    mutationFn: markNotificationRead,
  });
};
