import { useTags } from '../api/get-tags';
import { Tag } from '@/types/api';

export const TagsList = () => {
  const tagsQuery = useTags();

  if (tagsQuery.isLoading) {
    return <div>Loading...</div>;
  }

  if (tagsQuery.isError) {
    return <div>Error loading tags</div>;
  }

  const tags = tagsQuery.data?.data ?? [];

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Tags</h2>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag: Tag) => (
          <span
            key={tag.id}
            className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
            style={{ backgroundColor: tag.color, color: '#fff' }}
          >
            {tag.label}
          </span>
        ))}
      </div>
    </div>
  );
};
