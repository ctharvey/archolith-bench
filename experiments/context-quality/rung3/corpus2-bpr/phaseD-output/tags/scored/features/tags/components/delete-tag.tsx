import { Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useNotifications } from '@/components/ui/notifications';

import { useDeleteTag } from '../api/delete-tag';

type DeleteTagProps = {
  tagId: string;
};

export const DeleteTag = ({ tagId }: DeleteTagProps) => {
  const { addNotification } = useNotifications();
  const deleteTagMutation = useDeleteTag({
    mutationConfig: {
      onSuccess: () => {
        addNotification({
          type: 'success',
          title: 'Tag Deleted',
        });
      },
    },
  });

  return (
    <Button
      size="icon"
      variant="ghost"
      className="size-4 p-0 text-white hover:text-red-200"
      onClick={() => deleteTagMutation.mutate({ tagId })}
      isLoading={deleteTagMutation.isPending}
    >
      <Trash2 className="size-3" />
    </Button>
  );
};
