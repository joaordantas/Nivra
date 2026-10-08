export const DEFAULT_NOTIFICATION_PREFERENCES = Object.freeze({
  invoice_due_soon: true,
  invoice_overdue: true,
  card_limit: true,
  unusual_expense: true,
  weekly_summary: true,
  monthly_summary: true,
  budget_threshold: true,
  goal_progress: true,
});

export function createNotificationPreferenceState() {
  return {
    preferences: { ...DEFAULT_NOTIFICATION_PREFERENCES },
    loading: true,
    updatingKey: null,
    error: "",
    success: "",
  };
}

export function notificationPreferenceReducer(state, action) {
  switch (action.type) {
    case "load-start":
      return { ...state, loading: true, error: "", success: "" };
    case "load-success":
      return {
        ...state,
        preferences: { ...action.preferences },
        loading: false,
        error: "",
      };
    case "load-error":
      return { ...state, loading: false, error: action.message, success: "" };
    case "update-start":
      if (state.updatingKey !== null) return state;
      return { ...state, updatingKey: action.key, error: "", success: "" };
    case "update-success":
      return {
        ...state,
        preferences: { ...action.preferences },
        updatingKey: null,
        error: "",
        success: "Preferência salva.",
      };
    case "update-error":
      return { ...state, updatingKey: null, error: action.message, success: "" };
    default:
      return state;
  }
}
