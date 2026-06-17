import { TagsList } from './tags-list';
import { CreateTag } from './create-tag';

export const Tags = () => {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xl font-bold">Tags:</h3>
        <CreateTag />
      </div>
      <TagsList />
    </div>
  );
};
