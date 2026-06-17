import { ContentLayout } from '@/components/layout';
import { ProjectView } from '../components/project-view';

export const ProjectRoute = () => {
  return (
    <ContentLayout title="Project Details">
      <ProjectView />
    </ContentLayout>
  );
};
