import * as React from 'react';

import { useProject } from '../api/get-project';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/utils/format';

export const ProjectView = ({ projectId }: { projectId: string }) => {
  const projectQuery = useProject({ projectId });

  if (projectQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const project = projectQuery.data?.data;

  if (!project) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">{project.name}</h1>
        <Badge variant={project.status === 'ACTIVE' ? 'success' : 'warning'}>
          {project.status}
        </Badge>
      </div>
      <div>
        <p className="text-sm text-gray-500">Created: {formatDate(project.createdAt)}</p>
      </div>
      {project.description && (
        <div>
          <p className="text-gray-700">{project.description}</p>
        </div>
      )}
    </div>
  );
};
