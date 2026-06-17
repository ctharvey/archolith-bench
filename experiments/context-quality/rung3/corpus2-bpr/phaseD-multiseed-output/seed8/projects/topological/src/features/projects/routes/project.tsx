import { useParams } from 'react-router-dom';
import { ProjectDetail } from '../components/project-detail';

export const ProjectRoute = () => {
  const { projectId } = useParams<{ projectId: string }>();

  if (!projectId) {
    return <div>Project ID is required</div>;
  }

  return <ProjectDetail projectId={projectId} />;
};
