import { useProjects } from '../api/get-projects';
import { Project } from '@/types/api';
import { Link } from 'react-router-dom';
import { paths } from '@/config/paths';
import { formatDate } from '@/utils/format';

export const ProjectsList = () => {
  const projectsQuery = useProjects({ page: 1 });

  if (projectsQuery.isLoading) {
    return <div>Loading...</div>;
  }

  if (projectsQuery.isError) {
    return <div>Error loading projects</div>;
  }

  const projects = projectsQuery.data?.data ?? [];

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Projects</h2>
      <div className="grid gap-4">
        {projects.map((project: Project) => (
          <Link
            key={project.id}
            to={paths.app.project.getHref(project.id)}
            className="block p-4 border rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-semibold">{project.name}</h3>
                <p className="text-sm text-gray-500">
                  Created {formatDate(project.createdAt)}
                </p>
              </div>
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
          </Link>
        ))}
      </div>
    </div>
  );
};
