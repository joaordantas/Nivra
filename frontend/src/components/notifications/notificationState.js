export const NOTIFICATION_PAGE_SIZE = 12;

const ALLOWED_NOTIFICATION_ROUTES = new Set([
  "/dashboard",
  "/transactions",
  "/installments",
  "/accounts",
  "/cards",
  "/budgets",
  "/goals",
  "/lumi",
  "/settings",
]);

export function safeNotificationRoute(metadata) {
  const route = metadata?.route;
  return typeof route === "string" && ALLOWED_NOTIFICATION_ROUTES.has(route)
    ? route
    : null;
}

export function formatUnreadBadge(count) {
  if (count <= 0) return null;
  return count > 99 ? "99+" : String(count);
}

export function createNotificationState() {
  return {
    open: false,
    filter: "all",
    items: [],
    unreadCount: 0,
    loading: false,
    loadingMore: false,
    hasMore: false,
    error: "",
    badgeError: false,
    mutatingId: null,
    markingAll: false,
  };
}

export function notificationReducer(state, action) {
  switch (action.type) {
    case "open":
      return { ...state, open: true };
    case "close":
      return { ...state, open: false };
    case "filter":
      return { ...state, filter: action.filter };
    case "unread-success":
      return { ...state, unreadCount: action.count, badgeError: false };
    case "unread-error":
      return { ...state, badgeError: true };
    case "list-start":
      return action.reset
        ? { ...state, loading: true, loadingMore: false, error: "" }
        : { ...state, loadingMore: true, error: "" };
    case "list-success": {
      const items = action.reset ? action.items : [...state.items, ...action.items];
      return {
        ...state,
        items,
        loading: false,
        loadingMore: false,
        hasMore: action.items.length === action.pageSize,
        error: "",
      };
    }
    case "list-error":
      return {
        ...state,
        loading: false,
        loadingMore: false,
        error: action.message,
      };
    case "mutation-start":
      return { ...state, mutatingId: action.id, error: "" };
    case "mutation-end":
      return { ...state, mutatingId: null };
    case "read-all-start":
      return { ...state, markingAll: true, error: "" };
    case "read-all-end":
      return { ...state, markingAll: false };
    default:
      return state;
  }
}
