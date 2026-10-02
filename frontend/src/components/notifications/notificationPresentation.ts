import {
  CreditCard,
  FileText,
  Gauge,
  Settings,
  Target,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import type { NotificationSeverity, NotificationType } from "../../types";

interface NotificationPresentation {
  icon: LucideIcon;
  label: string;
}

export const notificationTypePresentation: Record<NotificationType, NotificationPresentation> = {
  financial_alert: { icon: Wallet, label: "Financeiro" },
  card_alert: { icon: CreditCard, label: "Cartão" },
  budget_alert: { icon: Gauge, label: "Orçamento" },
  goal_alert: { icon: Target, label: "Meta" },
  system: { icon: Settings, label: "Sistema" },
  summary: { icon: FileText, label: "Resumo" },
};

export const severityLabels: Record<NotificationSeverity, string> = {
  info: "Informativa",
  warning: "Atenção",
  critical: "Importante",
};

function isSameDay(first: Date, second: Date) {
  return first.getFullYear() === second.getFullYear()
    && first.getMonth() === second.getMonth()
    && first.getDate() === second.getDate();
}

export function formatNotificationDate(value: string, now = new Date()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Data indisponível";
  const elapsedMinutes = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 60_000));
  if (elapsedMinutes < 1) return "Agora";
  if (elapsedMinutes < 60) return `Há ${elapsedMinutes} min`;
  const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date);
  if (isSameDay(date, now)) return `Hoje, ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (isSameDay(date, yesterday)) return `Ontem, ${time}`;
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
  }).format(date);
}
