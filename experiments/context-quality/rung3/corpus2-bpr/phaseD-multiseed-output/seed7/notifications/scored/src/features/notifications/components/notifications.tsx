import { NotificationsList } from './notifications-list';

export const Notifications = () => {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xl font-bold">Notifications</h3>
      </div>
      <NotificationsList />
    </div>
  );
};
