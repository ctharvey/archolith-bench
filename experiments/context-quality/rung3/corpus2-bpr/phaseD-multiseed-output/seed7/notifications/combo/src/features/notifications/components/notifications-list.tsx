import { ArchiveX } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { formatDate } from '@/utils/format';

import { useNotifications } from '../api/get-notifications';
import { useMarkNotificationRead } from '../api/mark-notification-read';

export const NotificationsList = () => {
  const notificationsQuery = useNotifications();
  const markReadMutation = useMarkNotificationRead();

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
          className={`w-full bg-white p-4 shadow-sm ${!notification.read ? 'border-l-4 border-blue-500' : ''}`}
        >
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <p className="text-sm">{notification.message}</p>
              <span className="text-xs text-gray-500">
                {formatDate(notification.createdAt)}
              </span>
            </div>
            {!notification.read && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  markReadMutation.mutate({
                    data: { notificationId: notification.id },
                  })
                }
                isLoading={markReadMutation.isPending}
              >
                Mark as Read
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
};
