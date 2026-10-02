import { Bell } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type MouseEvent,
  type ReactNode,
} from "react";

import { ApiError, api } from "../../services/api";
import type { Notification } from "../../types";
import {
  createNotificationState,
  formatUnreadBadge,
  NOTIFICATION_PAGE_SIZE,
  notificationReducer,
  type NotificationFilter,
} from "./notificationState";

export interface NotificationCenterContextValue {
  state: ReturnType<typeof createNotificationState>;
  closePanel: () => void;
  deleteNotification: (notification: Notification) => Promise<void>;
  loadMore: () => Promise<void>;
  markAllRead: () => Promise<void>;
  markRead: (notification: Notification) => Promise<void>;
  openPanel: (trigger: HTMLButtonElement) => void;
  retry: () => Promise<void>;
  setFilter: (filter: NotificationFilter) => void;
}

const NotificationCenterContext = createContext<NotificationCenterContextValue | null>(null);

function readableError(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Não foi possível carregar suas notificações. Tente novamente.";
}

export function NotificationCenterProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(notificationReducer, undefined, createNotificationState);
  const lastTriggerRef = useRef<HTMLButtonElement | null>(null);

  const refreshUnreadCount = useCallback(async () => {
    try {
      const response = await api.getNotificationUnreadCount();
      dispatch({ type: "unread-success", count: response.unread_count });
    } catch {
      dispatch({ type: "unread-error" });
    }
  }, []);

  const loadNotifications = useCallback(async (
    reset: boolean,
    filter: NotificationFilter,
  ) => {
    dispatch({ type: "list-start", reset });
    try {
      const items = await api.getNotifications({
        limit: NOTIFICATION_PAGE_SIZE,
        offset: reset ? 0 : state.items.length,
        unreadOnly: filter === "unread",
      });
      dispatch({
        type: "list-success",
        reset,
        items,
        pageSize: NOTIFICATION_PAGE_SIZE,
      });
    } catch (error) {
      dispatch({ type: "list-error", message: readableError(error) });
    }
  }, [state.items.length]);

  useEffect(() => {
    void refreshUnreadCount();
  }, [refreshUnreadCount]);

  const refreshPanel = useCallback(async (filter = state.filter) => {
    await Promise.all([
      loadNotifications(true, filter),
      refreshUnreadCount(),
    ]);
  }, [loadNotifications, refreshUnreadCount, state.filter]);

  function openPanel(trigger: HTMLButtonElement) {
    lastTriggerRef.current = trigger;
    dispatch({ type: "open" });
    void refreshPanel();
  }

  const closePanel = useCallback(() => {
    dispatch({ type: "close" });
    requestAnimationFrame(() => lastTriggerRef.current?.focus());
  }, []);

  function setFilter(filter: NotificationFilter) {
    dispatch({ type: "filter", filter });
    void loadNotifications(true, filter);
  }

  async function mutateNotification(notification: Notification, operation: () => Promise<unknown>) {
    if (state.mutatingId !== null || state.markingAll) return;
    dispatch({ type: "mutation-start", id: notification.id });
    try {
      await operation();
      await refreshPanel();
    } catch (error) {
      dispatch({ type: "list-error", message: readableError(error) });
    } finally {
      dispatch({ type: "mutation-end" });
    }
  }

  async function markRead(notification: Notification) {
    if (notification.lida) return;
    await mutateNotification(notification, () => api.markNotificationRead(notification.id));
  }

  async function deleteNotification(notification: Notification) {
    await mutateNotification(notification, () => api.deleteNotification(notification.id));
  }

  async function markAllRead() {
    if (state.markingAll || state.mutatingId !== null || state.unreadCount === 0) return;
    dispatch({ type: "read-all-start" });
    try {
      await api.markAllNotificationsRead();
      await refreshPanel();
    } catch (error) {
      dispatch({ type: "list-error", message: readableError(error) });
    } finally {
      dispatch({ type: "read-all-end" });
    }
  }

  const value: NotificationCenterContextValue = {
    state,
    closePanel,
    deleteNotification,
    loadMore: () => loadNotifications(false, state.filter),
    markAllRead,
    markRead,
    openPanel,
    retry: () => refreshPanel(),
    setFilter,
  };

  return (
    <NotificationCenterContext.Provider value={value}>
      {children}
    </NotificationCenterContext.Provider>
  );
}

export function useNotificationCenter() {
  const context = useContext(NotificationCenterContext);
  if (!context) throw new Error("NotificationCenter precisa do provider correspondente.");
  return context;
}

export function NotificationBell({ variant }: { variant: "desktop" | "mobile" }) {
  const { openPanel, state } = useNotificationCenter();
  const badge = formatUnreadBadge(state.unreadCount);
  const unreadLabel = state.unreadCount === 1
    ? "1 notificação não lida"
    : `${state.unreadCount} notificações não lidas`;

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    openPanel(event.currentTarget);
  }

  return (
    <button
      aria-expanded={state.open}
      aria-haspopup="dialog"
      aria-label={`Abrir notificações, ${unreadLabel}`}
      className={`notification-bell notification-bell-${variant}`}
      onClick={handleClick}
      type="button"
    >
      <Bell aria-hidden="true" size={19} />
      {variant === "desktop" ? <span>Notificações</span> : null}
      {badge ? <span aria-hidden="true" className="notification-badge">{badge}</span> : null}
      {state.badgeError ? <span aria-live="polite" className="sr-only">A contagem não pôde ser atualizada.</span> : null}
    </button>
  );
}
