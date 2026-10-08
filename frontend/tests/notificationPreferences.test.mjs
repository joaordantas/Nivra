import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  createNotificationPreferenceState,
  notificationPreferenceReducer,
} from "../src/components/notifications/notificationPreferenceState.js";

test("inicia em loading com todas as preferências retrocompatíveis", () => {
  const state = createNotificationPreferenceState();
  assert.equal(state.loading, true);
  assert.deepEqual(state.preferences, DEFAULT_NOTIFICATION_PREFERENCES);
  assert.equal(state.preferences.weekly_summary, true);
  assert.equal(state.preferences.monthly_summary, true);
  assert.equal(state.preferences.budget_threshold, true);
  assert.equal(state.preferences.goal_progress, true);
});

test("carrega e preserva o estado retornado após reload", () => {
  const persisted = { ...DEFAULT_NOTIFICATION_PREFERENCES, unusual_expense: false };
  const state = notificationPreferenceReducer(createNotificationPreferenceState(), {
    type: "load-success",
    preferences: persisted,
  });
  assert.equal(state.loading, false);
  assert.equal(state.preferences.unusual_expense, false);
});

test("só confirma a alteração após resposta persistida", () => {
  const initial = notificationPreferenceReducer(createNotificationPreferenceState(), {
    type: "load-success",
    preferences: DEFAULT_NOTIFICATION_PREFERENCES,
  });
  const saving = notificationPreferenceReducer(initial, { type: "update-start", key: "card_limit" });
  assert.equal(saving.preferences.card_limit, true);
  assert.equal(saving.updatingKey, "card_limit");

  const saved = notificationPreferenceReducer(saving, {
    type: "update-success",
    preferences: { ...DEFAULT_NOTIFICATION_PREFERENCES, card_limit: false },
  });
  assert.equal(saved.preferences.card_limit, false);
  assert.equal(saved.updatingKey, null);
  assert.equal(saved.success, "Preferência salva.");
});

test("erro mantém o último estado confirmado", () => {
  const loaded = notificationPreferenceReducer(createNotificationPreferenceState(), {
    type: "load-success",
    preferences: { ...DEFAULT_NOTIFICATION_PREFERENCES, invoice_overdue: false },
  });
  const saving = notificationPreferenceReducer(loaded, { type: "update-start", key: "invoice_overdue" });
  const failed = notificationPreferenceReducer(saving, { type: "update-error", message: "Falha controlada" });
  assert.equal(failed.preferences.invoice_overdue, false);
  assert.equal(failed.updatingKey, null);
  assert.equal(failed.error, "Falha controlada");
});

test("ignora cliques repetidos enquanto uma atualização está ativa", () => {
  const state = notificationPreferenceReducer(createNotificationPreferenceState(), {
    type: "update-start",
    key: "unusual_expense",
  });
  const repeated = notificationPreferenceReducer(state, { type: "update-start", key: "card_limit" });
  assert.equal(repeated, state);
  assert.equal(repeated.updatingKey, "unusual_expense");
});
