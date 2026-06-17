import { Tag } from '@/types/api';

type TagCardProps = {
  tag: Tag;
};

export const TagCard = ({ tag }: TagCardProps) => {
  return (
    <div className="border rounded-lg p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <div
          className="w-4 h-4 rounded-full"
          style={{ backgroundColor: tag.color }}
        />
        <span className="font-medium">{tag.label}</span>
      </div>
    </div>
  );
};
