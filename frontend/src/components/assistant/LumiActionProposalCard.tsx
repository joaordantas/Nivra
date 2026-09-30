import { AlertTriangle, CheckCircle2, CircleX, Clock3, PencilLine, ReceiptText } from "lucide-react";

import type { LumiActionProposal } from "../../types";
import { Link } from "react-router-dom";
import { Button } from "../ui/Button";
import { formatCurrency, formatDate } from "../../utils/formatters";

interface LumiActionProposalCardProps {
  proposal: LumiActionProposal;
  onCancel: (confirmationId: string) => void;
  onConfirm: (confirmationId: string) => void;
  pendingAction: "confirm" | "cancel" | null;
}

function formattedAmount(value: string | null): string {
  if (!value) return "Não informado";
  return formatCurrency(Number(value));
}

function formattedDate(value: unknown): string {
  return typeof value === "string" && value ? formatDate(value) : "Não informada";
}

export function LumiActionProposalCard({ proposal, onCancel, onConfirm, pendingAction }: LumiActionProposalCardProps) {
  const isExpense = proposal.action_type === "create_expense";
  const isUpdate = proposal.action_type === "update_transaction";
  const confirmation = proposal.confirmation;
  const canAct = confirmation?.status === "pending" && pendingAction === null;
  const actionLabel = isUpdate ? "alteração" : isExpense ? "despesa" : "receita";
  const executionAmount = isUpdate
    ? String((proposal.payload.after as Record<string, unknown> | null)?.amount ?? "")
    : proposal.payload.amount;

  return (
    <section className="lumi-action-proposal" aria-label={`Proposta de ${actionLabel}`}>
      <div className="lumi-action-proposal-heading">
        <span className="lumi-action-proposal-icon" aria-hidden="true"><Clock3 size={16} /></span>
        <div>
          <strong>{isUpdate ? "Revisar alteração" : `Revisar ${actionLabel}`}</strong>
          <p>{proposal.summary}</p>
        </div>
      </div>
      {isUpdate && proposal.payload.before && proposal.payload.after ? (
        <div className="lumi-action-change-list" aria-label="Comparação da alteração">
          <span className="lumi-action-section-label"><PencilLine size={14} /> O que a Lumi entendeu</span>
          {proposal.payload.changes?.includes("description") ? <div><strong>Descrição</strong><span>{String(proposal.payload.before.comentario ?? "Não informada")}</span><b aria-hidden="true">→</b><span>{String(proposal.payload.after.description ?? "Não informada")}</span></div> : null}
          {proposal.payload.changes?.includes("amount") ? <div><strong>Valor</strong><span>{formattedAmount(String(proposal.payload.before.valor))}</span><b aria-hidden="true">→</b><span>{formattedAmount(String(proposal.payload.after.amount))}</span></div> : null}
          {proposal.payload.changes?.includes("date") ? <div><strong>Data</strong><span>{formattedDate(proposal.payload.before.data)}</span><b aria-hidden="true">→</b><span>{formattedDate(proposal.payload.after.date)}</span></div> : null}
          {proposal.payload.changes?.includes("category") ? <div><strong>Categoria</strong><span>{String(proposal.payload.before.categoria)}</span><b aria-hidden="true">→</b><span>{String((proposal.payload.after.category as { name?: string })?.name ?? "Não informada")}</span></div> : null}
          {proposal.payload.changes?.includes("account") ? <div><strong>Conta</strong><span>{String(proposal.payload.before.conta)}</span><b aria-hidden="true">→</b><span>{String((proposal.payload.after.account as { name?: string })?.name ?? "Não informada")}</span></div> : null}
        </div>
      ) : null}
      {!isUpdate ? <><span className="lumi-action-section-label"><ReceiptText size={14} /> O que será registrado</span><dl className="lumi-action-proposal-details">
        <div><dt>Valor</dt><dd>{formattedAmount(proposal.payload.amount)}</dd></div>
        <div><dt>Descrição</dt><dd>{proposal.payload.description ?? "Não informada"}</dd></div>
        <div><dt>Conta</dt><dd>{proposal.payload.account?.name ?? "Não informada"}</dd></div>
        <div><dt>Categoria</dt><dd>{proposal.payload.category?.name ?? "Não informada"}</dd></div>
        <div><dt>Data</dt><dd>{formattedDate(proposal.payload.date)}</dd></div>
      </dl></> : null}
      {proposal.missing_fields.length > 0 ? <p className="lumi-action-note"><AlertTriangle size={15} />Faltam: {proposal.missing_fields.join(", ")}.</p> : null}
      {proposal.warnings.map((warning) => <p className="lumi-action-note" key={warning}><AlertTriangle size={15} />{warning}</p>)}
      {confirmation ? (
        <>
          <p className="lumi-action-disclaimer">{proposal.execution_enabled
            ? "Confira os dados. Ao confirmar, a movimentação será registrada na sua conta."
            : "A confirmação valida apenas a proposta. Nenhuma movimentação financeira será criada nesta versão."}</p>
          {confirmation.status === "executed" ? <Link to="/transactions">Ver movimentações</Link> : null}
          {confirmation.status === "executed" ? <p className="lumi-action-status success"><CheckCircle2 size={15} />Alteração salva no Nivra.</p> : null}
          {confirmation.status === "cancelled" ? <p className="lumi-action-status"><CircleX size={15} />Proposta cancelada. Nada foi alterado.</p> : null}
          {confirmation.status === "pending" ? (
            <div className="lumi-action-proposal-actions">
              <Button disabled={!canAct} onClick={() => onConfirm(confirmation.confirmation_id)} type="button">
                <CheckCircle2 aria-hidden="true" size={16} />
                {pendingAction === "confirm" ? "Executando com segurança..." : `Confirmar ${actionLabel}${executionAmount ? ` de ${formattedAmount(executionAmount)}` : ""}`}
              </Button>
              <Button disabled={!canAct} onClick={() => onCancel(confirmation.confirmation_id)} type="button" variant="secondary">
                <CircleX aria-hidden="true" size={16} />
                {pendingAction === "cancel" ? "Cancelando..." : "Cancelar proposta"}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
