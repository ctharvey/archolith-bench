import { useProjects } from '../api/get-projects';
import { Project } from '@/types/api';

export const ProjectsList = () => {
  const projectsQuery = useProjects();

  if (projectsQuery.isLoading) {
    return <div>Loading...</div>;
  }

  if (projectsQuery.isError) {
    return <div>Error loading projects</div>;
  }

  const projects = projectsQuery.data?.data ?? [];

  return (
    <div className="space-y-4">
      {projects.map((project: Project) => (
        <div key={project.id} className="border rounded-lg p-4 shadow-sm">
          <h3 className="text-lg font-semibold">{project.name}</h3>
          <span className="inline-block px-2 py-1 text-sm rounded bg-blue-100 text-blue-800">
            {project.status}
          </span>
        </div>
      ))}
    </div>
  );
};
