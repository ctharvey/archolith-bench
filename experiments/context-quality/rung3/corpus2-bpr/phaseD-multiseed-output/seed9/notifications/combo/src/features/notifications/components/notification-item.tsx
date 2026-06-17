import { Button } from '@/components/ui/button';
import { useNotifications as useAppNotifications } from '@/components/ui/notifications';
import { Notification } from '@/types/api';
import { formatDate } from '@/utils/format';

import { useMarkNotificationRead } from '../api/mark-notification-read';

type NotificationItemProps = {
  notification: Notification;
};

export const NotificationItem = ({ notification }: NotificationItemProps) => {
  const { addNotification } = useAppNotifications();
  const markNotificationReadMutation = useMarkNotificationRead({
    mutationConfig: {
      onSuccess: () => {
        addNotification({
          type: 'success',
          title: 'Notification Marked as Read',
        });
      },
    },
  });

  return (
    <li
      aria-label={`notification-${notification.id}`}
      className={`w-full bg-white p-4 shadow-sm ${!notification.read ? 'border-l-4 border-blue-500' : ''}`}
    >
      <div className="flex justify-between">
        <div>
          <p className="text-sm font-medium">{notification.message}</p>
          <span className="text-xs text-gray-500">
            {formatDate(notification.createdAt)}
          </span>
        </div>
        {!notification.read && (
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              markNotificationReadMutation.mutate({
                notificationId: notification.id,
              })
            }
            isLoading={markNotificationReadMutation.isPending}
          >
            Mark as Read
          </Button>
        )}
      </div>
    </li>
  );
};
