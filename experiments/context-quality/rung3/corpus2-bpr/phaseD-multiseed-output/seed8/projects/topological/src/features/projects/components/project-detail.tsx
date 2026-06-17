import { useProject } from '../api/get-project';
import { formatDate } from '@/utils/format';

export const ProjectDetail = ({ projectId }: { projectId: string }) => {
  const projectQuery = useProject({ projectId });

  if (projectQuery.isLoading) {
    return <div>Loading...</div>;
  }

  if (projectQuery.isError) {
    return <div>Error loading project</div>;
  }

  const project = projectQuery.data?.data;

  if (!project) {
    return <div>Project not found</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">{project.name}</h2>
      <div className="flex items-center gap-2">
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${
            project.status === 'ACTIVE'
              ? 'bg-green-100 text-green-800'
              : project.status === 'COMPLETED'
              ? 'bg-blue-100 text-blue-800'
              : 'bg-gray-100 text-gray-800'
          }`}
        >
          {project.status}
        </span>
      </div>
      <p className="text-sm text-gray-500">
        Created {formatDate(project.createdAt)}
      </p>
    </div>
  );
};
