import { ChevronLeft, ChevronRight, Pencil, Plus, Target, Trash2, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../app/providers";
import { budgetBalanceLabel, clampProgress, monthLabel, shiftMonth } from "../components/budgets/budgetPresentation";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Budget, Category } from "../types";
import { formatCurrency } from "../utils/formatters";

function currentPeriod() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function BudgetsPage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState(currentPeriod);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Budget | null>(null);
  const [categoryId, setCategoryId] = useState(0);
  const [limit, setLimit] = useState("");

  const availableCategories = useMemo(() => {
    const used = new Set(budgets.map((budget) => budget.category.id));
    return categories.filter((category) => !used.has(category.id) && !["income", "transfers"].includes(category.system_key ?? ""));
  }, [budgets, categories]);

  async function load() {
    if (!user) return;
    try {
      setLoading(true);
      const [budgetData, categoryData] = await Promise.all([api.getBudgets(period), api.getCategories()]);
      setBudgets(budgetData);
      setCategories(categoryData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar os orçamentos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [user?.id, period]);

  function openCreate() {
    setCategoryId(availableCategories[0]?.id ?? 0);
    setLimit("");
    setCreating(true);
  }

  function openEdit(budget: Budget) {
    setEditing(budget);
    setLimit(budget.limit);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!categoryId || !limit) return;
    try {
      setSaving(true);
      await api.createBudget({ category_id: categoryId, period, limit });
      setCreating(false);
      setMessage("Orçamento criado com sucesso.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar o orçamento.");
    } finally {
      setSaving(false);
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || !limit) return;
    try {
      setSaving(true);
      await api.updateBudget(editing.id, limit);
      setEditing(null);
      setMessage("Limite atualizado.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar o orçamento.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(budget: Budget) {
    if (!window.confirm(`Excluir o orçamento de ${budget.category.name}? As despesas serão preservadas.`)) return;
    try {
      await api.deleteBudget(budget.id);
      setMessage("Orçamento excluído. Nenhuma movimentação financeira foi alterada.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível excluir o orçamento.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader description="Planeje seus gastos mensais por categoria sem alterar seu saldo." eyebrow="Planejamento mensal" title="Orçamentos" />
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}

      <Card as="section" className="budget-toolbar">
        <div className="budget-period" aria-label="Período do orçamento">
          <button aria-label="Mês anterior" className="icon-button" onClick={() => setPeriod(shiftMonth(period, -1))} type="button"><ChevronLeft size={18} /></button>
          <div><small>Período</small><strong>{monthLabel(period)}</strong></div>
          <button aria-label="Próximo mês" className="icon-button" onClick={() => setPeriod(shiftMonth(period, 1))} type="button"><ChevronRight size={18} /></button>
        </div>
        <div className="budget-toolbar-actions">
          {period !== currentPeriod() ? <Button onClick={() => setPeriod(currentPeriod())} type="button" variant="secondary">Mês atual</Button> : null}
          <Button disabled={loading || availableCategories.length === 0} onClick={openCreate} type="button"><Plus size={18} />Novo orçamento</Button>
        </div>
      </Card>

      <section aria-busy={loading} aria-label={`Orçamentos de ${monthLabel(period)}`} className="budget-grid">
        {loading ? [1, 2, 3].map((item) => <span className="surface-card skeleton budget-card-skeleton" key={item} />) : null}
        {!loading && budgets.length === 0 ? (
          <Card className="budget-empty-card"><EmptyState action={<Button disabled={availableCategories.length === 0} onClick={openCreate} type="button"><Plus size={18} />Criar orçamento</Button>} description="Defina quanto pretende gastar por categoria neste mês." icon={Target} title="Nenhum orçamento definido" /></Card>
        ) : null}
        {!loading && budgets.map((budget) => {
          const spent = Number(budget.spent);
          const total = Number(budget.limit);
          const percentage = Number(budget.usage_percentage);
          const balance = budgetBalanceLabel(budget.remaining);
          return (
            <Card className={`budget-card ${balance.kind === "exceeded" ? "budget-card-exceeded" : ""}`} key={budget.id}>
              <div className="budget-card-heading"><span className="budget-icon"><WalletCards size={19} /></span><div><small>Categoria</small><h2>{budget.category.name}</h2></div><div className="row-actions"><button aria-label={`Editar orçamento de ${budget.category.name}`} className="icon-button" onClick={() => openEdit(budget)} type="button"><Pencil size={16} /></button><button aria-label={`Excluir orçamento de ${budget.category.name}`} className="icon-button icon-button-danger" onClick={() => void remove(budget)} type="button"><Trash2 size={16} /></button></div></div>
              <div className="budget-values"><strong>{formatCurrency(spent)} <span>de {formatCurrency(total)}</span></strong><b>{percentage.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%</b></div>
              <div aria-label={`${percentage}% do orçamento utilizado`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={clampProgress(percentage)} className="budget-progress" role="progressbar"><i style={{ width: `${clampProgress(percentage)}%` }} /></div>
              <p className={balance.kind}>{balance.kind === "exceeded" ? `${formatCurrency(balance.amount)} acima do orçamento` : `${formatCurrency(balance.amount)} restantes`}</p>
            </Card>
          );
        })}
      </section>

      {creating ? <Modal onClose={() => setCreating(false)} title="Novo orçamento"><form className="form-grid" onSubmit={submitCreate}><label>Categoria<select autoFocus onChange={(event) => setCategoryId(Number(event.target.value))} required value={categoryId}>{availableCategories.map((category) => <option key={category.id} value={category.id}>{category.nome}</option>)}</select></label><label>Limite mensal<input inputMode="decimal" min="0.01" onChange={(event) => setLimit(event.target.value)} placeholder="R$ 0,00" required step="0.01" type="number" value={limit} /></label><small className="field-hint">Categoria e período não poderão ser alterados depois da criação.</small><Button disabled={saving || !categoryId || Number(limit) <= 0} type="submit">{saving ? "Salvando..." : "Criar orçamento"}</Button></form></Modal> : null}
      {editing ? <Modal onClose={() => setEditing(null)} title={`Editar ${editing.category.name}`}><form className="form-grid" onSubmit={submitEdit}><label>Novo limite mensal<input autoFocus inputMode="decimal" min="0.01" onChange={(event) => setLimit(event.target.value)} required step="0.01" type="number" value={limit} /></label><small className="field-hint">O período e a categoria permanecem inalterados.</small><Button disabled={saving || Number(limit) <= 0} type="submit">{saving ? "Salvando..." : "Salvar limite"}</Button></form></Modal> : null}
    </div>
  );
}
