export function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

export function formatDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);

  if (!year || !month || !day) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
  }).format(new Date(year, month - 1, day));
}

export function getCurrentMonthRange() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  const lastDay = String(new Date(year, today.getMonth() + 1, 0).getDate()).padStart(2, "0");

  return {
    start: `${year}-${month}-01`,
    end: `${year}-${month}-${day}`,
    monthEnd: `${year}-${month}-${lastDay}`,
    label: new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(today),
  };
}
