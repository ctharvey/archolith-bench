import { BaseEntity } from '@/types/api';

export type Tag = BaseEntity & {
  label: string;
  color: string;
};
