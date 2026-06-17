import * as React from 'react';
import { useParams } from 'react-router-dom';

import { ContentLayout } from '@/components/layout';
import { ProjectView } from '../components/project';

export const ProjectRoute = () => {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <ContentLayout title="Project Details">
      <ProjectView projectId={projectId} />
    </ContentLayout>
  );
};
