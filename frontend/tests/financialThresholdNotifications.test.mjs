import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../src/", import.meta.url);

test("preferências exibem controles de orçamento e metas", async () => {
  const source = await readFile(new URL("components/notifications/NotificationPreferences.tsx", root), "utf8");
  assert.match(source, /budget_threshold/);
  assert.match(source, /goal_progress/);
  assert.match(source, /Alertas de orçamento/);
  assert.match(source, /Progresso de metas/);
});

test("central reutiliza apresentações e rotas seguras para os novos tipos", async () => {
  const presentation = await readFile(new URL("components/notifications/notificationPresentation.ts", root), "utf8");
  const panel = await readFile(new URL("components/notifications/NotificationPanel.tsx", root), "utf8");
  assert.match(presentation, /budget_alert: \{ icon: Gauge, label: "Orçamento" \}/);
  assert.match(presentation, /goal_alert: \{ icon: Target, label: "Meta" \}/);
  assert.match(panel, /safeNotificationRoute/);
  assert.match(panel, /severity-/);
});

test("preferências novas permanecem habilitadas por padrão", async () => {
  const source = await readFile(new URL("components/notifications/notificationPreferenceState.js", root), "utf8");
  assert.match(source, /budget_threshold: true/);
  assert.match(source, /goal_progress: true/);
});
