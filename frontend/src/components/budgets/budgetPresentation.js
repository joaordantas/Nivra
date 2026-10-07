export function clampProgress(value) {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(value, 100);
}

export function budgetBalanceLabel(remaining) {
  const value = Number(remaining);
  if (value < 0) return { kind: "exceeded", amount: Math.abs(value) };
  return { kind: "remaining", amount: value };
}

export function shiftMonth(period, delta) {
  const [year, month] = period.split("-").map(Number);
  const next = new Date(year, month - 1 + delta, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

export function monthLabel(period) {
  const [year, month] = period.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" })
    .format(new Date(year, month - 1, 1));
}
