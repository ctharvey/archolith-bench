import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Notification } from '@/types/api';

type GetNotificationsResponse = {
  data: Notification[];
};

export const getNotifications = (): Promise<GetNotificationsResponse> => {
  return api.get('/notifications');
};

export const getNotificationsQueryOptions = () => ({
  queryKey: ['notifications'],
  queryFn: () => getNotifications(),
});

type UseNotificationsOptions = {
  queryConfig?: QueryConfig<typeof getNotifications>;
};

export const useNotifications = ({ queryConfig }: UseNotificationsOptions = {}) => {
  return useQuery({
    ...getNotificationsQueryOptions(),
    ...queryConfig,
  });
};
