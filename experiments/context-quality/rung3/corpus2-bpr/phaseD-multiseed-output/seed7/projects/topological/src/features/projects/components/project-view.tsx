import { useParams } from 'react-router-dom';

import { useProject } from '../api/get-project';
import { Spinner } from '@/components/ui/spinner';
import { formatDate } from '@/utils/format';

export const ProjectView = () => {
  const { projectId } = useParams();
  const projectQuery = useProject({ projectId: projectId! });

  if (projectQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const project = projectQuery.data?.data;

  if (!project) {
    return <div>Project not found</div>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold">{project.name}</h1>
      <div className="mt-4 space-y-2">
        <div>
          <span className="font-medium">Status: </span>
          <span>{project.status}</span>
        </div>
        <div>
          <span className="font-medium">Created: </span>
          <span>{formatDate(project.createdAt)}</span>
        </div>
      </div>
    </div>
  );
};
