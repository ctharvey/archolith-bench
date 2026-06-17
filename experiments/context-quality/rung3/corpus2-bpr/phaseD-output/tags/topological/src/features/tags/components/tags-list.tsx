import { useTags } from '../api/get-tags';

import { Spinner } from '@/components/ui/spinner';
import { Table } from '@/components/ui/table';

export const TagsList = () => {
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
      <div className="flex h-48 w-full items-center justify-center">
        <p className="text-gray-500">No tags found.</p>
      </div>
    );
  }

  return (
    <Table
      data={tags}
      columns={[
        {
          title: 'Label',
          field: 'label',
        },
        {
          title: 'Color',
          field: 'color',
          Cell({ entry: { color } }) {
            return (
              <div className="flex items-center gap-2">
                <div
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span>{color}</span>
              </div>
            );
          },
        },
      ]}
    />
  );
};
