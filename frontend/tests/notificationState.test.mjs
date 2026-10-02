import assert from "node:assert/strict";
import test from "node:test";

import {
  createNotificationState,
  formatUnreadBadge,
  notificationReducer,
} from "../src/components/notifications/notificationState.js";

function notification(id, read = false) {
  return {
    id,
    tipo: "system",
    severidade: "info",
    titulo: `Notificação ${id}`,
    mensagem: "Mensagem",
    metadados: {},
    chave_dedupe: `test:${id}`,
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
