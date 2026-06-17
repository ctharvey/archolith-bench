import { useSearchParams } from 'react-router';

import { Spinner } from '@/components/ui/spinner';
import { Table } from '@/components/ui/table';

import { useTags } from '../api/get-tags';

export const TagsList = () => {
  const [searchParams] = useSearchParams();

  const tagsQuery = useTags({
    page: +(searchParams.get('page') || 1),
  });

  if (tagsQuery.isLoading) {
    return (
      <div className="flex h-48 w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const tags = tagsQuery.data?.data;
  const meta = tagsQuery.data?.meta;

  if (!tags) return null;

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
      pagination={
        meta && {
          totalPages: meta.totalPages,
          currentPage: meta.page,
          rootUrl: '',
        }
      }
    />
  );
};
