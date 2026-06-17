import { ContentLayout } from '@/components/layouts/content-layout';
import { TagsList } from '../components/tags-list';

export const TagsListRoute = () => {
  return (
    <ContentLayout title="Tags">
      <TagsList />
    </ContentLayout>
  );
};
