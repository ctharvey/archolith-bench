import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useProjects } from '../api/get-projects';
import { paths } from '@/config/paths';
import { Spinner } from '@/components/ui/spinner';
import { Table, Pagination } from '@/components/ui/table';
import { formatDate } from '@/utils/format';

export const ProjectsList = () => {
  const [page, setPage] = useState(1);
  const projectsQuery = useProjects({ page });

  if (projectsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const projects = projectsQuery.data?.data ?? [];
  const meta = projectsQuery.data?.meta;

  return (
    <div className="flex flex-col">
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
            Cell: ({ entry: { status } }) => {
              const statusColors: Record<string, string> = {
                ACTIVE: 'text-green-600',
                COMPLETED: 'text-blue-600',
                ARCHIVED: 'text-gray-500',
              };
              return (
                <span className={`font-medium ${statusColors[status]}`}>
                  {status}
                </span>
              );
            },
          },
          {
            title: 'Created At',
            field: 'createdAt',
            Cell: ({ entry: { createdAt } }) => (
              <span>{formatDate(createdAt)}</span>
            ),
          },
          {
            title: '',
            field: 'id',
            Cell: ({ entry: { id } }) => (
              <Link
                to={paths.app.project.getHref(id)}
                className="text-blue-600 hover:text-blue-800"
              >
                View
              </Link>
            ),
          },
        ]}
      />
      {meta && (
        <Pagination
          page={page}
          totalPages={meta.totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
};
