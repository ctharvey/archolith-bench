import { ArchiveX } from 'lucide-react';

import { Spinner } from '@/components/ui/spinner';

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

  if (!projects?.length) {
    return (
      <div
        role="list"
        aria-label="projects"
        className="flex h-40 flex-col items-center justify-center bg-white text-gray-500"
      >
        <ArchiveX className="size-10" />
        <h4>No Projects Found</h4>
      </div>
    );
  }

  return (
    <ul aria-label="projects" className="flex flex-col space-y-3">
      {projects.map((project) => (
        <li
          key={project.id}
          className="w-full bg-white p-4 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-lg font-semibold">{project.name}</span>
            <span className={`text-sm font-medium ${
              project.status === 'active' ? 'text-green-600' : 'text-gray-500'
            }`}>
              {project.status}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
};
