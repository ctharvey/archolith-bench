import { ContentLayout } from '@/components/layouts';
import { TagsList } from '../components/tags-list';

export const TagsListRoute = () => {
  return (
    <ContentLayout title="Tags">
      <TagsList />
    </ContentLayout>
  );
};
