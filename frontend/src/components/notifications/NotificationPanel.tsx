import {
  CheckCheck,
  Inbox,
  LoaderCircle,
  MoreHorizontal,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef } from "react";

import type { Notification } from "../../types";
import { Button } from "../ui/Button";
import { Feedback } from "../ui/Feedback";
import { useNotificationCenter } from "./NotificationCenter";
import {
  formatNotificationDate,
  notificationTypePresentation,
  severityLabels,
} from "./notificationPresentation";
import { safeNotificationRoute } from "./notificationState";

function NotificationItemContent({ notification }: { notification: Notification }) {
  const presentation = notificationTypePresentation[notification.tipo];
  const Icon = presentation.icon;
  return (
    <>
      <span aria-hidden="true" className={`notification-type-icon severity-${notification.severidade}`}>
        <Icon size={19} />
      </span>
      <span className="notification-copy">
        <span className="notification-item-meta">
          <span>{presentation.label}</span>
          <span aria-hidden="true">·</span>
          <span>{severityLabels[notification.severidade]}</span>
          <time dateTime={notification.criada_em}>{formatNotificationDate(notification.criada_em)}</time>
        </span>
        <strong>{notification.titulo}</strong>
        <span className="notification-message">{notification.mensagem}</span>
        {!notification.lida ? <span className="sr-only">Não lida.</span> : null}
      </span>
      {!notification.lida ? <span aria-hidden="true" className="notification-unread-dot" /> : null}
    </>
  );
}

function NotificationItem({ notification }: { notification: Notification }) {
  const { activateNotification, deleteNotification, state } = useNotificationCenter();
  const busy = state.mutatingId === notification.id;
  const route = safeNotificationRoute(notification.metadados);
  const interactive = !notification.lida || route !== null;

  return (
    <article className={`notification-item${notification.lida ? " is-read" : " is-unread"}`} role="listitem">
      {!interactive ? (
        <div className="notification-item-content">
          <NotificationItemContent notification={notification} />
        </div>
      ) : (
        <button
          aria-label={route ? `Abrir: ${notification.titulo}` : `Marcar como lida: ${notification.titulo}`}
          className="notification-item-content notification-read-button"
          disabled={busy}
          onClick={() => void activateNotification(notification)}
          type="button"
        >
          <NotificationItemContent notification={notification} />
        </button>
      )}
      <details className="notification-item-menu">
        <summary aria-label={`Ações para ${notification.titulo}`}>
          {busy ? <LoaderCircle aria-hidden="true" className="spin" size={17} /> : <MoreHorizontal aria-hidden="true" size={18} />}
        </summary>
        <div role="menu">
          <button
            disabled={busy}
            onClick={() => void deleteNotification(notification)}
            role="menuitem"
            type="button"
          >
            <Trash2 aria-hidden="true" size={16} />
            Excluir
          </button>
        </div>
      </details>
    </article>
  );
}

function NotificationSkeletons() {
  return (
    <div aria-label="Carregando notificações" className="notification-skeleton-list" role="status">
      {[0, 1, 2].map((item) => (
        <div className="notification-skeleton" key={item}>
          <span />
          <div><span /><span /><span /></div>
        </div>
      ))}
    </div>
  );
}

export function NotificationPanel() {
  const {
    closePanel,
    loadMore,
    markAllRead,
    retry,
    setFilter,
    state,
  } = useNotificationCenter();
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!state.open) return;
    closeButtonRef.current?.focus();
    document.body.classList.add("notification-center-open");

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePanel();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(
        "button:not([disabled]), summary, [href], input:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("notification-center-open");
    };
  }, [closePanel, state.open]);

  if (!state.open) return null;

  return (
    <>
      <button aria-label="Fechar notificações" className="notification-backdrop" onClick={closePanel} type="button" />
      <aside
        aria-labelledby="notification-center-title"
        aria-modal="true"
        className="notification-panel"
        ref={panelRef}
        role="dialog"
      >
        <header className="notification-panel-header">
          <div>
            <span className="section-kicker">Seu espaço</span>
            <h2 id="notification-center-title">Notificações</h2>
          </div>
          <button aria-label="Fechar notificações" className="icon-button" onClick={closePanel} ref={closeButtonRef} type="button">
            <X aria-hidden="true" size={20} />
          </button>
        </header>

        <div className="notification-toolbar">
          <div aria-label="Filtrar notificações" className="notification-filters" role="group">
            <button aria-pressed={state.filter === "all"} onClick={() => setFilter("all")} type="button">Todas</button>
            <button aria-pressed={state.filter === "unread"} onClick={() => setFilter("unread")} type="button">Não lidas</button>
          </div>
          {state.unreadCount > 0 ? (
            <button
              className="notification-read-all"
              disabled={state.markingAll || state.mutatingId !== null}
              onClick={() => void markAllRead()}
              type="button"
            >
              {state.markingAll ? <LoaderCircle aria-hidden="true" className="spin" size={16} /> : <CheckCheck aria-hidden="true" size={16} />}
              Marcar todas como lidas
            </button>
          ) : null}
        </div>

        {state.error ? (
          <div className="notification-error">
            <Feedback>{state.error}</Feedback>
            <Button onClick={() => void retry()} type="button" variant="secondary">
              <RefreshCw aria-hidden="true" size={16} /> Tentar novamente
            </Button>
          </div>
        ) : null}

        <div aria-live="polite" className="notification-list" role="list">
          {state.loading && state.items.length === 0 ? <NotificationSkeletons /> : null}
          {!state.loading && state.items.length === 0 && !state.error ? (
            <div className="notification-empty">
              <span><Inbox aria-hidden="true" size={22} /></span>
              <strong>{state.filter === "unread" ? "Tudo em dia" : "Nenhuma notificação por enquanto"}</strong>
              <p>{state.filter === "unread" ? "Você não tem notificações não lidas." : "Quando houver novidades internas, elas aparecerão aqui."}</p>
            </div>
          ) : null}
          {state.items.map((notification) => (
            <NotificationItem key={notification.id} notification={notification} />
          ))}
        </div>

        {state.hasMore ? (
          <footer className="notification-panel-footer">
            <Button disabled={state.loadingMore} onClick={() => void loadMore()} type="button" variant="secondary">
              {state.loadingMore ? <LoaderCircle aria-hidden="true" className="spin" size={16} /> : null}
              {state.loadingMore ? "Carregando..." : "Carregar mais"}
            </Button>
          </footer>
        ) : null}
      </aside>
    </>
  );
}
