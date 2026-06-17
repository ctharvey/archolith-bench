import { ArchiveX } from 'lucide-react';

import { Spinner } from '@/components/ui/spinner';

import { useTags } from '../api/get-tags';

export const TagsList = () => {
  const tagsQuery = useTags();

  if (tagsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const tags = tagsQuery.data;

  if (!tags?.length) {
    return (
      <div
        role="list"
        aria-label="tags"
        className="flex h-40 flex-col items-center justify-center bg-white text-gray-500"
      >
        <ArchiveX className="size-10" />
        <h4>No Tags Found</h4>
      </div>
    );
  }

  return (
    <ul aria-label="tags" className="flex flex-wrap gap-2">
      {tags.map((tag) => (
        <li
          key={tag.id}
          className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium"
          style={{
            backgroundColor: tag.color + '20',
            color: tag.color,
            border: `1px solid ${tag.color}`,
          }}
        >
          {tag.label}
        </li>
      ))}
    </ul>
  );
};
