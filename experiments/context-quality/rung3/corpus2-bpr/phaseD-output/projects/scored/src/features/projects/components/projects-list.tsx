import { Spinner } from '@/components/ui/spinner';
import { Table } from '@/components/ui/table';
import { formatDate } from '@/utils/format';

import { useProjects } from '../api/get-projects';

import { DeleteProject } from './delete-project';

export const ProjectsList = () => {
  const projectsQuery = useProjects();

  if (projectsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const projects = projectsQuery.data?.data;

  if (!projects) return null;

  return (
    <Table
      data={projects}
      columns={[
        {
          title: 'Name',
          field: 'name',
        },
        {
          title: 'Status',
          field: 'status',
        },
        {
          title: 'Created At',
          field: 'createdAt',
          Cell({ entry: { createdAt } }) {
            return <span>{formatDate(createdAt)}</span>;
          },
        },
        {
          title: '',
          field: 'id',
          Cell({ entry: { id } }) {
            return <DeleteProject id={id} />;
          },
        },
      ]}
    />
  );
};
