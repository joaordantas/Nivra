import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const app = read("../src/App.tsx");
const layout = read("../src/components/layout/AppLayout.tsx");
const router = read("../src/app/router.tsx");
const transactions = read("../src/pages/TransactionsPage.tsx");
const api = read("../src/services/api.ts");

test("error boundary protects the whole application", () => {
  assert.match(app, /AppErrorBoundary/);
});

test("keyboard users receive a skip link and focusable main content", () => {
  assert.match(layout, /className="skip-link"/);
  assert.match(layout, /id="main-content"/);
  assert.match(layout, /tabIndex=\{-1\}/);
});

test("privacy and terms are public routes", () => {
  assert.match(router, /path: "\/privacy"/);
  assert.match(router, /path: "\/terms"/);
});

test("transaction history uses server filters and pagination", () => {
  assert.match(api, /getMovementPage/);
  assert.match(api, /movement_type/);
  assert.match(transactions, /PAGE_SIZE = 25/);
  assert.match(transactions, /Paginação das movimentações/);
  assert.match(transactions, /movementPage\.summary/);
});

test("authenticated layout includes dismissible onboarding", () => {
  assert.match(layout, /OnboardingChecklist/);
});
