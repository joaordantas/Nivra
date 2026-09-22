import { AlertTriangle, CheckCircle2, CircleX, Clock3 } from "lucide-react";

import type { LumiActionProposal } from "../../types";
import { Link } from "react-router-dom";
import { Button } from "../ui/Button";

interface LumiActionProposalCardProps {
  proposal: LumiActionProposal;
  onCancel: (confirmationId: string) => void;
  onConfirm: (confirmationId: string) => void;
  pendingAction: "confirm" | "cancel" | null;
}

function formattedAmount(value: string | null): string {
  if (!value) return "Não informado";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

export function LumiActionProposalCard({ proposal, onCancel, onConfirm, pendingAction }: LumiActionProposalCardProps) {
  const isExpense = proposal.action_type === "create_expense";
  const confirmation = proposal.confirmation;
  const canAct = confirmation?.status === "pending" && pendingAction === null;
  const actionLabel = isExpense ? "despesa" : "receita";

  return (
    <section className="lumi-action-proposal" aria-label={`Proposta de ${actionLabel}`}>
      <div className="lumi-action-proposal-heading">
        <span className="lumi-action-proposal-icon" aria-hidden="true"><Clock3 size={16} /></span>
        <div>
          <strong>Proposta para revisão</strong>
          <p>{proposal.summary}</p>
        </div>
      </div>
      <dl className="lumi-action-proposal-details">
        <div><dt>Valor</dt><dd>{formattedAmount(proposal.payload.amount)}</dd></div>
        <div><dt>Descrição</dt><dd>{proposal.payload.description ?? "Não informada"}</dd></div>
        <div><dt>Conta</dt><dd>{proposal.payload.account?.name ?? "Não informada"}</dd></div>
        <div><dt>Categoria</dt><dd>{proposal.payload.category?.name ?? "Não informada"}</dd></div>
        <div><dt>Data</dt><dd>{proposal.payload.date ?? "Não informada"}</dd></div>
      </dl>
      {proposal.missing_fields.length > 0 ? <p className="lumi-action-note"><AlertTriangle size={15} />Faltam: {proposal.missing_fields.join(", ")}.</p> : null}
      {proposal.warnings.map((warning) => <p className="lumi-action-note" key={warning}><AlertTriangle size={15} />{warning}</p>)}
      {confirmation ? (
        <>
          <p className="lumi-action-disclaimer">{proposal.execution_enabled
            ? "Confira os dados. Ao confirmar, a movimentação será registrada na sua conta."
            : "A confirmação valida apenas a proposta. Nenhuma movimentação financeira será criada nesta versão."}</p>
          {confirmation.status === "executed" ? <Link to="/transactions">Ver movimentações</Link> : null}
          {confirmation.status === "pending" ? (
            <div className="lumi-action-proposal-actions">
              <Button disabled={!canAct} onClick={() => onConfirm(confirmation.confirmation_id)} type="button">
                <CheckCircle2 aria-hidden="true" size={16} />
                {pendingAction === "confirm" ? "Confirmando..." : `Confirmar ${actionLabel} de ${formattedAmount(proposal.payload.amount)}`}
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
