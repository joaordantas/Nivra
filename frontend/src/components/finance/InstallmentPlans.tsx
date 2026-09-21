import { CalendarRange, ChevronRight, Clock3, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { api } from "../../services/api";
import type { Account, Category, InstallmentPlanDetail, InstallmentPlanSummary } from "../../types";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Feedback } from "../ui/Feedback";
import { Modal } from "../ui/Modal";

interface InstallmentPlansProps {
  accounts: Account[];
  categories: Category[];
  createHref?: string;
  onChanged: () => Promise<void>;
  onSelectPlan: (planId: number | null) => void;
  refreshKey: number;
  selectedPlanId: number | null;
}

interface EditValues {
  descricao: string;
  categoriaId: number | null;
  contaId: number | null;
}

function editValuesFromPlan(plan: InstallmentPlanDetail): EditValues {
  const firstInstallment = plan.parcelas[0];
  return {
    descricao: plan.descricao,
    categoriaId: firstInstallment?.categoria_id ?? null,
    contaId: firstInstallment?.conta_id ?? null,
  };
}

export function InstallmentPlans({
  accounts,
  categories,
  createHref = "#new-transaction",
  onChanged,
  onSelectPlan,
  refreshKey,
  selectedPlanId,
}: InstallmentPlansProps) {
  const [plans, setPlans] = useState<InstallmentPlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<InstallmentPlanDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState<EditValues | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadPlans() {
    try {
      setLoading(true);
      setPlans(await api.getInstallmentPlans());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar os parcelamentos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadPlans(); }, [refreshKey]);

  useEffect(() => {
    if (selectedPlanId === null) {
      setDetail(null);
      setEditing(false);
      setEditValues(null);
      return;
    }
    async function loadDetail() {
      try {
        setDetailLoading(true);
        setError("");
        const result = await api.getInstallmentPlan(selectedPlanId as number);
        setDetail(result);
        setEditValues(editValuesFromPlan(result));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Não foi possível abrir o parcelamento.");
        onSelectPlan(null);
      } finally {
        setDetailLoading(false);
      }
    }
    void loadDetail();
  }, [selectedPlanId]);

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !editValues || saving) return;
    try {
      setSaving(true);
      const updated = await api.updateInstallmentPlan(detail.id, {
        descricao: editValues.descricao,
        categoria_id: editValues.categoriaId,
        conta_id: editValues.contaId,
      });
      setDetail(updated);
      setEditValues(editValuesFromPlan(updated));
      setEditing(false);
      setMessage("Parcelamento atualizado em todas as parcelas.");
      setError("");
      await Promise.all([loadPlans(), onChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar o parcelamento.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!detail || deleting) return;
    const confirmed = window.confirm(
      `Excluir o parcelamento “${detail.descricao}”? Todas as ${detail.quantidade_parcelas} parcelas relacionadas serão removidas.`,
    );
    if (!confirmed) return;
    try {
      setDeleting(true);
      await api.deleteInstallmentPlan(detail.id);
      onSelectPlan(null);
      setMessage("Parcelamento e parcelas relacionadas foram excluídos.");
      setError("");
      await Promise.all([loadPlans(), onChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível excluir o parcelamento.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Card as="section" className="installment-plans-card">
      <div className="card-heading card-heading-row">
        <div><span className="section-kicker">Planejamento</span><h2>Parcelamentos</h2></div>
        <span className="count-badge">{plans.length}</span>
      </div>
      <p className="installment-section-description">Acompanhe as datas de cada parcela sem tratá-las automaticamente como pagas.</p>
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}

      {loading ? (
        <div className="installment-plan-list" aria-label="Carregando parcelamentos">
          {[1, 2].map((item) => <span className="skeleton skeleton-row" key={item} />)}
        </div>
      ) : plans.length === 0 ? (
        <EmptyState
          action={<a className="button button-secondary" href={createHref}>Criar parcelamento</a>}
          description="Selecione Parcelado ao registrar uma receita ou despesa."
          icon={CalendarRange}
          title="Nenhum parcelamento"
        />
      ) : (
        <div className="installment-plan-list">
          {plans.map((plan) => {
            const percentage = Math.min(100, Math.round(plan.parcelas_com_data_atingida * 100 / plan.quantidade_parcelas));
            return (
              <button className="installment-plan-row" key={plan.id} onClick={() => onSelectPlan(plan.id)} type="button">
                <span className="installment-plan-icon"><CalendarRange aria-hidden="true" size={19} /></span>
                <span className="installment-plan-main">
                  <span><strong>{plan.descricao}</strong><b>{formatCurrency(plan.valor_total)}</b></span>
                  <small>{plan.parcelas_com_data_atingida} de {plan.quantidade_parcelas} datas atingidas · {plan.proxima_parcela_data ? `próxima em ${formatDate(plan.proxima_parcela_data)}` : "calendário concluído"}</small>
                  <span className="installment-progress" aria-label={`${percentage}% do calendário atingido`}><i style={{ width: `${percentage}%` }} /></span>
                </span>
                <ChevronRight aria-hidden="true" size={18} />
              </button>
            );
          })}
        </div>
      )}

      {selectedPlanId !== null ? (
        <Modal onClose={() => onSelectPlan(null)} title={detail?.descricao ?? "Parcelamento"}>
          {detailLoading || !detail ? (
            <div className="installment-detail-loading"><span className="skeleton skeleton-value" /><span className="skeleton skeleton-row" /></div>
          ) : (
            <div className="installment-detail">
              {editing && editValues ? (
                <form className="form-grid installment-edit-form" onSubmit={handleUpdate}>
                  <Feedback tone="info">Valor, quantidade e datas ficam protegidos nesta etapa para preservar os lançamentos já registrados.</Feedback>
                  <label>Descrição<input autoFocus maxLength={255} onChange={(event) => setEditValues((current) => current ? { ...current, descricao: event.target.value } : current)} value={editValues.descricao} /></label>
                  <label>Categoria<select onChange={(event) => setEditValues((current) => current ? { ...current, categoriaId: event.target.value ? Number(event.target.value) : null } : current)} value={editValues.categoriaId ?? ""}><option value="">Sem categoria</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.nome}</option>)}</select></label>
                  <label>Conta<select onChange={(event) => setEditValues((current) => current ? { ...current, contaId: event.target.value ? Number(event.target.value) : null } : current)} value={editValues.contaId ?? ""}><option value="">Sem conta</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.nome}</option>)}</select></label>
                  <div className="installment-detail-actions"><Button disabled={saving || !editValues.descricao.trim()} type="submit">{saving ? "Salvando..." : "Salvar no grupo"}</Button><Button disabled={saving} onClick={() => { setEditing(false); setEditValues(editValuesFromPlan(detail)); }} type="button" variant="secondary">Cancelar</Button></div>
                </form>
              ) : (
                <>
                  <div className="installment-detail-summary">
                    <span><small>Valor total</small><strong>{formatCurrency(detail.valor_total)}</strong></span>
                    <span><small>Calendário</small><strong>{detail.parcelas_com_data_atingida}/{detail.quantidade_parcelas}</strong></span>
                    <span><small>Período</small><strong>{formatDate(detail.primeira_parcela_data)} – {formatDate(detail.ultima_parcela_data)}</strong></span>
                  </div>
                  <Feedback tone="info">“Data atingida” indica apenas a posição no calendário; não confirma pagamento.</Feedback>
                  <div className="installment-detail-actions"><Button onClick={() => setEditing(true)} type="button" variant="secondary"><Pencil size={16} />Editar grupo</Button><Button disabled={deleting} onClick={() => void handleDelete()} type="button" variant="danger"><Trash2 size={16} />{deleting ? "Excluindo..." : "Excluir grupo"}</Button></div>
                  <div className="installment-detail-list">
                    {detail.parcelas.map((installment) => (
                      <div className="installment-detail-row" key={installment.id}>
                        <span className="installment-number">{installment.numero_parcela}/{installment.quantidade_parcelas}</span>
                        <span><strong>{formatCurrency(installment.valor)}</strong><small>{formatDate(installment.data)} · {installment.categoria} · {installment.conta}</small></span>
                        <span className={`installment-temporal-status ${installment.status_temporal}`}><Clock3 size={13} />{installment.status_temporal === "futura" ? "Futura" : "Data atingida"}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </Modal>
      ) : null}
    </Card>
  );
}
