// Add Notification type to existing types
export type Notification = Entity<{
  message: string;
  read: boolean;
  userId: string;
}>;
