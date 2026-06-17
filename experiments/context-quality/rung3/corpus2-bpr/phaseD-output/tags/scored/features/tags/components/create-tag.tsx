import { Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Form, FormDrawer, Input } from '@/components/ui/form';
import { useNotifications } from '@/components/ui/notifications';

import { useCreateTag, createTagInputSchema } from '../api/create-tag';

export const CreateTag = () => {
  const { addNotification } = useNotifications();
  const createTagMutation = useCreateTag({
    mutationConfig: {
      onSuccess: () => {
        addNotification({
          type: 'success',
          title: 'Tag Created',
        });
      },
    },
  });

  return (
    <FormDrawer
      isDone={createTagMutation.isSuccess}
      triggerButton={
        <Button size="sm" icon={<Plus className="size-4" />}>
          Create Tag
        </Button>
      }
      title="Create Tag"
      submitButton={
        <Button
          isLoading={createTagMutation.isPending}
          form="create-tag"
          type="submit"
          size="sm"
          disabled={createTagMutation.isPending}
        >
          Submit
        </Button>
      }
    >
      <Form
        id="create-tag"
        onSubmit={(values) => {
          createTagMutation.mutate({ data: values });
        }}
        schema={createTagInputSchema}
        options={{
          defaultValues: {
            label: '',
            color: '#3b82f6',
          },
        }}
      >
        {({ register, formState }) => (
          <>
            <Input
              label="Label"
              error={formState.errors['label']}
              registration={register('label')}
            />
            <Input
              label="Color"
              type="color"
              error={formState.errors['color']}
              registration={register('color')}
            />
          </>
        )}
      </Form>
    </FormDrawer>
  );
};
