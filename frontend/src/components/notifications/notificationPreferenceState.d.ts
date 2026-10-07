import type { NotificationPreferenceKey, NotificationPreferences } from "../../types";

export const DEFAULT_NOTIFICATION_PREFERENCES: Readonly<NotificationPreferences>;

export interface NotificationPreferenceState {
  preferences: NotificationPreferences;
  loading: boolean;
  updatingKey: NotificationPreferenceKey | null;
  error: string;
  success: string;
}

export type NotificationPreferenceAction =
  | { type: "load-start" }
  | { type: "load-success"; preferences: NotificationPreferences }
  | { type: "load-error"; message: string }
  | { type: "update-start"; key: NotificationPreferenceKey }
  | { type: "update-success"; preferences: NotificationPreferences }
  | { type: "update-error"; message: string };

export function createNotificationPreferenceState(): NotificationPreferenceState;
export function notificationPreferenceReducer(
  state: NotificationPreferenceState,
  action: NotificationPreferenceAction,
): NotificationPreferenceState;
