// Add Notification type to existing types
export type Notification = Entity<{
  message: string;
  userId: string;
  read: boolean;
}>;
