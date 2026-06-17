import { ArchiveX } from 'lucide-react';

import { Spinner } from '@/components/ui/spinner';

import { useNotifications } from '../api/get-notifications';

import { NotificationItem } from './notification-item';

export const NotificationsList = () => {
  const notificationsQuery = useNotifications();

  if (notificationsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const notifications = notificationsQuery.data?.data;

  if (!notifications?.length) {
    return (
      <div
        role="list"
        aria-label="notifications"
        className="flex h-40 flex-col items-center justify-center bg-white text-gray-500"
      >
        <ArchiveX className="size-10" />
        <h4>No Notifications Found</h4>
      </div>
    );
  }

  return (
    <ul aria-label="notifications" className="flex flex-col space-y-3">
      {notifications.map((notification, index) => (
        <NotificationItem
          key={notification.id || index}
          notification={notification}
        />
      ))}
    </ul>
  );
};
