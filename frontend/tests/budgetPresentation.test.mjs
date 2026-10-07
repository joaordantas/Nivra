import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  budgetBalanceLabel,
  clampProgress,
  monthLabel,
  shiftMonth,
} from "../src/components/budgets/budgetPresentation.js";

const page = readFileSync(new URL("../src/pages/BudgetsPage.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("barra limita apenas a largura visual", () => {
  assert.equal(clampProgress(135), 100);
  assert.equal(clampProgress(77.5), 77.5);
  assert.equal(clampProgress(-2), 0);
});

test("overspend preserva o valor real acima do orçamento", () => {
  assert.deepEqual(budgetBalanceLabel("-100.00"), { kind: "exceeded", amount: 100 });
  assert.deepEqual(budgetBalanceLabel("180.00"), { kind: "remaining", amount: 180 });
});

test("mudança de mês atravessa dezembro e fevereiro", () => {
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2028-03", -1), "2028-02");
  assert.match(monthLabel("2026-10"), /outubro/i);
});

test("tela cobre loading e empty state com CTA", () => {
  assert.match(page, /aria-busy=\{loading\}/);
  assert.match(page, /Nenhum orçamento definido/);
  assert.match(page, /Criar orçamento/);
});

test("tela oferece criação, edição e exclusão", () => {
  assert.match(page, /api\.createBudget/);
  assert.match(page, /api\.updateBudget/);
  assert.match(page, /api\.deleteBudget/);
});

test("erros da API e conflitos são apresentados", () => {
  assert.match(page, /setError\(err instanceof Error \? err\.message/);
  assert.match(page, /<Feedback>\{error\}<\/Feedback>/);
});

test("progresso mantém percentual real acessível", () => {
  assert.match(page, /aria-label=\{`\$\{percentage\}% do orçamento utilizado`\}/);
  assert.match(page, /clampProgress\(percentage\)/);
});

test("layout possui breakpoint móvel sem overflow da grade", () => {
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*\.budget-grid \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.match(styles, /\.budget-card \{ display: grid;[\s\S]*min-width: 0;/);
});

test("cards usam tokens compartilhados compatíveis com temas claro e escuro", () => {
  assert.match(styles, /\.budget-progress[^}]*background: var\(--neutral-soft\)/);
  assert.match(styles, /\.budget-card-exceeded[^}]*color: var\(--danger\)/);
});
