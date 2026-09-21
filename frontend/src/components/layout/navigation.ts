import {
  Bot,
  CalendarRange,
  ChartNoAxesCombined,
  CreditCard,
  Landmark,
  ListChecks,
  PiggyBank,
  ReceiptText,
  Settings,
  Tags,
  Target,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavigationItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

export const primaryNavigation: NavigationItem[] = [
  { label: "Início", path: "/dashboard", icon: ChartNoAxesCombined },
  { label: "Transações", path: "/transactions", icon: ReceiptText },
  { label: "Parcelamentos", path: "/installments", icon: CalendarRange },
  { label: "Contas", path: "/accounts", icon: Landmark },
  { label: "Cartões", path: "/cards", icon: CreditCard },
  { label: "Orçamentos", path: "/budgets", icon: ListChecks },
  { label: "Metas", path: "/goals", icon: Target },
  { label: "Lumi", path: "/assistant", icon: Bot },
];

export const secondaryNavigation: NavigationItem[] = [
  { label: "Configurações", path: "/settings", icon: Settings },
];

export const mobileNavigation: NavigationItem[] = [
  { label: "Início", path: "/dashboard", icon: ChartNoAxesCombined },
  { label: "Histórico", path: "/transactions", icon: ReceiptText },
  { label: "Contas", path: "/accounts", icon: Landmark },
];

export const mobileMoreFinanceNavigation: NavigationItem[] = [
  { label: "Parcelamentos", path: "/installments", icon: CalendarRange },
  { label: "Cartões", path: "/cards", icon: CreditCard },
  { label: "Orçamentos", path: "/budgets", icon: ListChecks },
  { label: "Metas", path: "/goals", icon: Target },
  { label: "Lumi", path: "/assistant", icon: Bot },
];

export const mobileMoreSettingsNavigation: NavigationItem[] = [
  ...secondaryNavigation,
  { label: "Categorias", path: "/settings/categories", icon: Tags },
];

export const productIcon = PiggyBank;
