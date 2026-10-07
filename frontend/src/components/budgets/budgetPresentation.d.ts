export function clampProgress(value: number): number;
export function budgetBalanceLabel(remaining: string | number): { kind: "exceeded" | "remaining"; amount: number };
export function shiftMonth(period: string, delta: number): string;
export function monthLabel(period: string): string;
