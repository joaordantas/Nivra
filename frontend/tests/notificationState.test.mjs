import assert from "node:assert/strict";
import test from "node:test";

import {
  createNotificationState,
  formatUnreadBadge,
  notificationReducer,
  safeNotificationRoute,
} from "../src/components/notifications/notificationState.js";

function notification(id, read = false) {
  return {
    id,
    tipo: "system",
    severidade: "info",
    titulo: `Notificação ${id}`,
    mensagem: "Mensagem",
    metadados: {},
    lida: read,
    criada_em: "2026-10-02T12:00:00Z",
    lida_em: read ? "2026-10-02T12:05:00Z" : null,
  };
}

test("badge omite zero, exibe 1 e limita acima de 99", () => {
  assert.equal(formatUnreadBadge(0), null);
  assert.equal(formatUnreadBadge(1), "1");
  assert.equal(formatUnreadBadge(99), "99");
  assert.equal(formatUnreadBadge(100), "99+");
});

test("abre, fecha e alterna o filtro", () => {
  let state = createNotificationState();
  state = notificationReducer(state, { type: "open" });
  state = notificationReducer(state, { type: "filter", filter: "unread" });
  assert.equal(state.open, true);
  assert.equal(state.filter, "unread");
  state = notificationReducer(state, { type: "close" });
  assert.equal(state.open, false);
});

test("representa loading, lista, empty state e erro sem apagar a contagem", () => {
  let state = notificationReducer(createNotificationState(), { type: "unread-success", count: 7 });
  state = notificationReducer(state, { type: "list-start", reset: true });
  assert.equal(state.loading, true);
  state = notificationReducer(state, {
    type: "list-success",
    reset: true,
    items: [],
    pageSize: 12,
  });
  assert.deepEqual(state.items, []);
  assert.equal(state.loading, false);
  state = notificationReducer(state, { type: "list-error", message: "Falha controlada" });
  assert.equal(state.error, "Falha controlada");
  assert.equal(state.unreadCount, 7);
});

test("acumula paginação e encerra quando a página é incompleta", () => {
  const firstPage = Array.from({ length: 12 }, (_, index) => notification(index + 1));
  let state = notificationReducer(createNotificationState(), {
    type: "list-success",
    reset: true,
    items: firstPage,
    pageSize: 12,
  });
  assert.equal(state.hasMore, true);
  state = notificationReducer(state, { type: "list-start", reset: false });
  assert.equal(state.loadingMore, true);
  state = notificationReducer(state, {
    type: "list-success",
    reset: false,
    items: [notification(13)],
    pageSize: 12,
  });
  assert.equal(state.items.length, 13);
  assert.equal(state.hasMore, false);
});

test("controla mutações individuais e marcar todas sem cliques repetidos", () => {
  let state = createNotificationState();
  state = notificationReducer(state, { type: "mutation-start", id: 4 });
  assert.equal(state.mutatingId, 4);
  state = notificationReducer(state, { type: "mutation-end" });
  assert.equal(state.mutatingId, null);
  state = notificationReducer(state, { type: "read-all-start" });
  assert.equal(state.markingAll, true);
  state = notificationReducer(state, { type: "read-all-end" });
  assert.equal(state.markingAll, false);
});

test("falha do badge preserva o último valor conhecido", () => {
  let state = notificationReducer(createNotificationState(), { type: "unread-success", count: 3 });
  state = notificationReducer(state, { type: "unread-error" });
  assert.equal(state.unreadCount, 3);
  assert.equal(state.badgeError, true);
});

test("mantém resumo financeiro longo e metadata segura no centro", () => {
  const summary = {
    ...notification(75),
    tipo: "summary",
    titulo: "Seu resumo de setembro está pronto",
    mensagem: "Você recebeu R$ 12.345,67, gastou R$ 9.876,54 e terminou o período com saldo líquido de R$ 2.469,13. Sua maior categoria de gastos foi Alimentação e mercado.",
    metadados: {
      route: "/dashboard",
      source_type: "monthly_summary",
      source_id: "2026-09-01",
    },
  };
  const state = notificationReducer(createNotificationState(), {
    type: "list-success",
    reset: true,
    items: [summary],
    pageSize: 12,
  });
  assert.equal(state.items[0].tipo, "summary");
  assert.equal(state.items[0].mensagem, summary.mensagem);
  assert.deepEqual(Object.keys(state.items[0].metadados).sort(), ["route", "source_id", "source_type"]);
  assert.equal(safeNotificationRoute(state.items[0].metadados), "/dashboard");
  assert.equal(safeNotificationRoute({ route: "https://example.com" }), null);
  assert.equal(safeNotificationRoute({ route: "/admin" }), null);
});
