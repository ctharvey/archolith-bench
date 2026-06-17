import { ContentLayout } from '@/components/layout';
import { NotificationsList } from '../components/notifications-list';

export const NotificationsPage = () => {
  return (
    <ContentLayout title="Notifications">
      <NotificationsList />
    </ContentLayout>
  );
};
