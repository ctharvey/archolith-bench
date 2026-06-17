import { ArchiveX } from 'lucide-react';

import { Spinner } from '@/components/ui/spinner';
import { formatDate } from '@/utils/format';

import { useNotifications } from '../api/get-notifications';
import { MarkNotificationRead } from './mark-notification-read';

export const NotificationsList = () => {
  const notificationsQuery = useNotifications();

  if (notificationsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const notifications = notificationsQuery.data;

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
        <li
          aria-label={`notification-${notification.message}-${index}`}
          key={notification.id || index}
          className="w-full bg-white p-4 shadow-sm"
        >
          <div className="flex justify-between">
            <div>
              <span className="text-xs font-semibold">
                {formatDate(notification.createdAt)}
              </span>
            </div>
            <MarkNotificationRead notificationId={notification.id} />
          </div>
          <p className="mt-2">{notification.message}</p>
        </li>
      ))}
    </ul>
  );
};
