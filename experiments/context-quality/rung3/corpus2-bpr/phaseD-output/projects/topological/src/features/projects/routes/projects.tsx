import * as React from 'react';

import { ContentLayout } from '@/components/layout';
import { ProjectsList } from '../components/projects-list';

export const ProjectsRoute = () => {
  return (
    <ContentLayout title="Projects">
      <ProjectsList />
    </ContentLayout>
  );
};
