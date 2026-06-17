import { Check } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useNotifications } from '@/components/ui/notifications';

import { useMarkNotificationRead } from '../api/mark-notification-read';

type MarkNotificationReadProps = {
  notificationId: string;
};

export const MarkNotificationRead = ({ notificationId }: MarkNotificationReadProps) => {
  const { addNotification } = useNotifications();
  const markReadMutation = useMarkNotificationRead({
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
    <Button
      size="sm"
      variant="outline"
      icon={<Check className="size-4" />}
      isLoading={markReadMutation.isPending}
      onClick={() => markReadMutation.mutate({ notificationId })}
    >
      Mark as Read
    </Button>
  );
};
