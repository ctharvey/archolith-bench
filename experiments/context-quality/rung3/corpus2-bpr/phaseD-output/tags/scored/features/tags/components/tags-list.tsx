import { ArchiveX } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { useUser } from '@/lib/auth';
import { POLICIES, Authorization } from '@/lib/authorization';
import { User } from '@/types/api';

import { useTags } from '../api/get-tags';

import { DeleteTag } from './delete-tag';

export const TagsList = () => {
  const user = useUser();
  const tagsQuery = useTags();

  if (tagsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const tags = tagsQuery.data?.data;

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
          className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium"
          style={{ backgroundColor: tag.color, color: '#fff' }}
        >
          <span>{tag.label}</span>
          <Authorization
            policyCheck={POLICIES['tag:delete'](user.data as User, tag)}
          >
            <DeleteTag tagId={tag.id} />
          </Authorization>
        </li>
      ))}
    </ul>
  );
};
