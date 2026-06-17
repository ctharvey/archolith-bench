import { Trash } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ConfirmationDialog } from '@/components/ui/dialog';
import { useNotifications } from '@/components/ui/notifications';
import { Authorization, POLICIES } from '@/lib/authorization';

import { useDeleteProject } from '../api/delete-project';

type DeleteProjectProps = {
  id: string;
};

export const DeleteProject = ({ id }: DeleteProjectProps) => {
  const { addNotification } = useNotifications();
  const deleteProjectMutation = useDeleteProject({
    mutationConfig: {
      onSuccess: () => {
        addNotification({
          type: 'success',
          title: 'Project Deleted',
        });
      },
    },
  });

  return (
    <Authorization policyCheck={POLICIES['project:delete'](undefined)}>
      <ConfirmationDialog
        icon="danger"
        title="Delete Project"
        body="Are you sure you want to delete this project?"
        triggerButton={
          <Button icon={<Trash className="size-4" />} variant="danger" size="sm" />
        }
        confirmButton={
          <Button
            type="button"
            variant="danger"
            isLoading={deleteProjectMutation.isPending}
            onClick={() => deleteProjectMutation.mutate({ projectId: id })}
          >
            Delete Project
          </Button>
        }
      />
    </Authorization>
  );
};
