import { useParams } from 'react-router-dom';
import { useProject } from '../api/get-project';

export const ProjectRoute = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const projectQuery = useProject({ projectId: projectId! });

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
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">{project.name}</h1>
      <span className="inline-block px-2 py-1 text-sm rounded bg-blue-100 text-blue-800">
        {project.status}
      </span>
    </div>
  );
};
