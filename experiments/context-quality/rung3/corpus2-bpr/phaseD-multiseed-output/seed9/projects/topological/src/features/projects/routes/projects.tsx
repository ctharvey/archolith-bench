import { ProjectsList } from '../components/projects-list';

export const ProjectsRoute = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Projects</h1>
      <ProjectsList />
    </div>
  );
};
