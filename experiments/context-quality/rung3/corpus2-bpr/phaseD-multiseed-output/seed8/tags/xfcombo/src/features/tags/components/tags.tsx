import { TagsList } from './tags-list';

export const Tags = () => {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xl font-bold">Tags:</h3>
      </div>
      <TagsList />
    </div>
  );
};
