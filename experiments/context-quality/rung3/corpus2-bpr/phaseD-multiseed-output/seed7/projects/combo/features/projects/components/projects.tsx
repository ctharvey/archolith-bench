import { ProjectsList } from './projects-list';

export const Projects = () => {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xl font-bold">Projects</h3>
      </div>
      <ProjectsList />
    </div>
  );
};
