import { useTags } from '../api/get-tags';
import { Tag } from '../types';

export const TagList = () => {
  const tagsQuery = useTags();

  if (tagsQuery.isLoading) {
    return <div>Loading tags...</div>;
  }

  if (tagsQuery.isError) {
    return <div>Error loading tags: {tagsQuery.error?.message}</div>;
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
            style={{
              backgroundColor: tag.color,
              color: getContrastColor(tag.color),
            }}
          >
            {tag.label}
          </span>
        ))}
      </div>
    </div>
  );
};

function getContrastColor(hexColor: string): string {
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? '#000000' : '#ffffff';
}
