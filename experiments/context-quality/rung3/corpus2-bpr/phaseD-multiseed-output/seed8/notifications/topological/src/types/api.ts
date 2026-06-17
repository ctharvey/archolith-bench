// Add this type to the existing types/api.ts file
export type Notification = Entity<{
  message: string;
  userId: string;
  read: boolean;
}>;
