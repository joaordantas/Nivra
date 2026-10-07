import { BellRing } from "lucide-react";
import { useEffect, useReducer, useRef } from "react";

import type { NotificationPreferenceKey } from "../../types";
import { api } from "../../services/api";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import {
  createNotificationPreferenceState,
  notificationPreferenceReducer,
} from "./notificationPreferenceState";

const preferenceGroups: Array<{
  title: string;
  items: Array<{ key: NotificationPreferenceKey; label: string; description: string }>;
}> = [
  {
    title: "Faturas",
    items: [
      {
        key: "invoice_due_soon",
        label: "Faturas próximas do vencimento",
        description: "Receber aviso quando uma fatura estiver próxima da data de vencimento.",
      },
      {
        key: "invoice_overdue",
        label: "Faturas vencidas",
        description: "Receber alerta quando uma fatura estiver vencida e ainda pendente.",
      },
    ],
  },
  {
    title: "Cartões",
    items: [
      {
        key: "card_limit",
        label: "Limite do cartão",
        description: "Receber alertas quando o comprometimento do limite atingir níveis elevados.",
      },
    ],
  },
  {
    title: "Inteligência financeira",
    items: [
      {
        key: "unusual_expense",
        label: "Gastos incomuns",
        description: "Receber avisos quando a Nivra detectar um gasto fora do seu padrão habitual.",
      },
    ],
  },
  {
    title: "Resumos",
    items: [
      {
        key: "weekly_summary",
        label: "Resumo semanal",
        description: "Receba um resumo dos principais números da semana anterior.",
      },
      {
        key: "monthly_summary",
        label: "Resumo mensal",
        description: "Receba um resumo dos principais números do mês anterior.",
      },
    ],
  },
];

export function NotificationPreferences() {
  const [state, dispatch] = useReducer(
    notificationPreferenceReducer,
    undefined,
    createNotificationPreferenceState,
  );
  const mounted = useRef(true);

  async function loadPreferences() {
    dispatch({ type: "load-start" });
    try {
      const preferences = await api.getNotificationPreferences();
      if (mounted.current) dispatch({ type: "load-success", preferences });
    } catch {
      if (mounted.current) {
        dispatch({
          type: "load-error",
          message: "Não foi possível carregar suas preferências. Tente novamente.",
        });
      }
    }
  }

  useEffect(() => {
    mounted.current = true;
    void loadPreferences();
    return () => {
      mounted.current = false;
    };
  }, []);

  async function updatePreference(key: NotificationPreferenceKey, enabled: boolean) {
    if (state.updatingKey !== null) return;
    dispatch({ type: "update-start", key });
    try {
      const preferences = await api.updateNotificationPreferences({ [key]: enabled });
      if (mounted.current) dispatch({ type: "update-success", preferences });
    } catch {
      if (mounted.current) {
        dispatch({
          type: "update-error",
          message: "Não foi possível salvar a preferência. Nenhuma alteração foi aplicada.",
        });
      }
    }
  }

  return (
    <Card aria-busy={state.loading || state.updatingKey !== null} as="section" className="notification-preferences-card">
      <div className="notification-preferences-heading">
        <span className="settings-icon" aria-hidden="true"><BellRing size={21} /></span>
        <div>
          <h2>Notificações</h2>
          <p>Escolha quais alertas financeiros você deseja receber na Nivra.</p>
        </div>
      </div>

      {state.loading ? (
        <div aria-label="Carregando preferências de notificações" className="notification-preferences-loading" role="status">
          {Array.from({ length: 6 }, (_, index) => <span className="skeleton" key={index} />)}
        </div>
      ) : (
        <div className="notification-preference-groups">
          {preferenceGroups.map((group) => (
            <fieldset className="notification-preference-group" key={group.title}>
              <legend>{group.title}</legend>
              {group.items.map((item) => {
                const descriptionId = `notification-preference-${item.key}-description`;
                return (
                  <label className="notification-preference-row" htmlFor={`notification-preference-${item.key}`} key={item.key}>
                    <span className="notification-preference-copy">
                      <strong>{item.label}</strong>
                      <small id={descriptionId}>{item.description}</small>
                    </span>
                    <span className="notification-switch">
                      <input
                        aria-describedby={descriptionId}
                        checked={state.preferences[item.key]}
                        disabled={state.updatingKey !== null}
                        id={`notification-preference-${item.key}`}
                        onChange={(event) => void updatePreference(item.key, event.currentTarget.checked)}
                        role="switch"
                        type="checkbox"
                      />
                      <span aria-hidden="true" className="notification-switch-track"><span /></span>
                      {state.updatingKey === item.key ? <span className="sr-only">Salvando preferência.</span> : null}
                    </span>
                  </label>
                );
              })}
            </fieldset>
          ))}
        </div>
      )}

      {state.error ? (
        <div className="notification-preference-feedback">
          <p className="feedback feedback-error" role="alert">{state.error}</p>
          {state.loading ? null : <Button onClick={() => void loadPreferences()} type="button" variant="secondary">Tentar novamente</Button>}
        </div>
      ) : null}
      <p aria-live="polite" className="notification-preference-status">{state.success}</p>
    </Card>
  );
}
