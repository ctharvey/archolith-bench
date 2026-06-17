import { useNotifications } from '../api/get-notifications';
import { Notification } from '@/types/api';
import { formatDate } from '@/utils/format';

export const NotificationsList = () => {
  const notificationsQuery = useNotifications();
  const notifications = notificationsQuery.data?.data;

  if (notificationsQuery.isLoading) {
    return <div>Loading...</div>;
  }

  if (!notifications?.length) {
    return <div>No notifications found.</div>;
  }

  return (
    <div className="space-y-4">
      {notifications.map((notification: Notification) => (
        <div key={notification.id} className="rounded-md border p-4">
          <p className="text-sm">{notification.message}</p>
          <p className="mt-1 text-xs text-gray-500">
            {formatDate(notification.createdAt)}
          </p>
        </div>
      ))}
    </div>
  );
};
