import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Notification } from '@/features/notifications/types';

export const getNotifications = (): Promise<Notification[]> => {
  return api.get('/notifications');
};

export const getNotificationsQueryOptions = () => {
  return {
    queryKey: ['notifications'],
    queryFn: getNotifications,
  };
};

type UseNotificationsOptions = {
  queryConfig?: QueryConfig<typeof getNotificationsQueryOptions>;
};

export const useNotifications = ({
  queryConfig,
}: UseNotificationsOptions = {}) => {
  return useQuery({
    ...getNotificationsQueryOptions(),
    ...queryConfig,
  });
};
