import * as React from 'react';

import { useProjects } from '../api/get-projects';
import { Project } from '@/types/api';
import { Spinner } from '@/components/ui/spinner';
import { Table } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Link } from '@/components/ui/link';
import { paths } from '@/config/paths';

export const ProjectsList = () => {
  const projectsQuery = useProjects({ page: 1 });

  if (projectsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const projects = projectsQuery.data?.data;

  if (!projects) {
    return null;
  }

  return (
    <Table
      data={projects}
      columns={[
        {
          title: 'Name',
          field: 'name',
          Cell: ({ entry }: { entry: Project }) => (
            <Link
              to={paths.app.project.getHref(entry.id)}
              className="font-medium"
            >
              {entry.name}
            </Link>
          ),
        },
        {
          title: 'Status',
          field: 'status',
          Cell: ({ entry }: { entry: Project }) => (
            <Badge variant={entry.status === 'ACTIVE' ? 'success' : 'warning'}>
              {entry.status}
            </Badge>
          ),
        },
      ]}
    />
  );
};
