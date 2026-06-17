import { formatDate } from '@/utils/format';
import { Notification } from '@/features/notifications/types';
import { useMarkNotificationRead } from '@/features/notifications/api/mark-notification-read';
import { Button } from '@/components/ui/button';
import { Check } from 'lucide-react';

type NotificationItemProps = {
  notification: Notification;
};

export const NotificationItem = ({ notification }: NotificationItemProps) => {
  const markReadMutation = useMarkNotificationRead();

  return (
    <li
      aria-label={`notification-${notification.id}`}
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
            variant="ghost"
            icon={<Check className="size-4" />}
            onClick={() =>
              markReadMutation.mutate({ notificationId: notification.id })
            }
            isLoading={markReadMutation.isPending}
          >
            Mark Read
          </Button>
        )}
      </div>
    </li>
  );
};
