import { useNotifications } from '../api/get-notifications';
import { Notification } from '@/types/api';
import { formatDate } from '@/utils/format';

export const NotificationsList = () => {
  const notificationsQuery = useNotifications();
  const notifications = notificationsQuery.data?.data ?? [];

  if (notificationsQuery.isLoading) {
    return <div>Loading notifications...</div>;
  }

  if (notifications.length === 0) {
    return <div>No notifications yet.</div>;
  }

  return (
    <ul className="divide-y divide-gray-200">
      {notifications.map((notification: Notification) => (
        <li key={notification.id} className="py-4">
          <p className="text-sm text-gray-900">{notification.message}</p>
          <p className="text-xs text-gray-500 mt-1">
            {formatDate(notification.createdAt)}
          </p>
        </li>
      ))}
    </ul>
  );
};
