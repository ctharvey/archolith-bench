import { Spinner } from '@/components/ui/spinner';
import { Table } from '@/components/ui/table';

import { useProjects } from '../api/get-projects';

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
      ]}
    />
  );
};
