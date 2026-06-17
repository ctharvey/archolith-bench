import { infiniteQueryOptions, useInfiniteQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { Meta, Notification } from '@/types/api';

export const getNotifications = ({
  page = 1,
}: {
  page?: number;
}): Promise<{ data: Notification[]; meta: Meta }> => {
  return api.get(`/notifications`, {
    params: {
      page,
    },
  });
};

export const getInfiniteNotificationsQueryOptions = () => {
  return infiniteQueryOptions({
    queryKey: ['notifications'],
    queryFn: ({ pageParam = 1 }) => {
      return getNotifications({ page: pageParam as number });
    },
    getNextPageParam: (lastPage) => {
      if (lastPage?.meta?.page === lastPage?.meta?.totalPages) return undefined;
      const nextPage = lastPage.meta.page + 1;
      return nextPage;
    },
    initialPageParam: 1,
  });
};

type UseNotificationsOptions = {
  page?: number;
  queryConfig?: QueryConfig<typeof getNotifications>;
};

export const useInfiniteNotifications = () => {
  return useInfiniteQuery({
    ...getInfiniteNotificationsQueryOptions(),
  });
};
