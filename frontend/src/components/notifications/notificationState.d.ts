import type { Notification } from "../../types";

export const NOTIFICATION_PAGE_SIZE: number;

export type NotificationFilter = "all" | "unread";

export interface NotificationCenterState {
  open: boolean;
  filter: NotificationFilter;
  items: Notification[];
  unreadCount: number;
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  error: string;
  badgeError: boolean;
  mutatingId: number | null;
  markingAll: boolean;
}

export type NotificationAction =
  | { type: "open" }
  | { type: "close" }
  | { type: "filter"; filter: NotificationFilter }
  | { type: "unread-success"; count: number }
  | { type: "unread-error" }
  | { type: "list-start"; reset: boolean }
  | { type: "list-success"; reset: boolean; items: Notification[]; pageSize: number }
  | { type: "list-error"; message: string }
  | { type: "mutation-start"; id: number }
  | { type: "mutation-end" }
  | { type: "read-all-start" }
  | { type: "read-all-end" };

export function formatUnreadBadge(count: number): string | null;
export function safeNotificationRoute(metadata: Notification["metadados"]): string | null;
export function createNotificationState(): NotificationCenterState;
export function notificationReducer(
  state: NotificationCenterState,
  action: NotificationAction,
): NotificationCenterState;
