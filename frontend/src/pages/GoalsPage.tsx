import { Archive, CalendarDays, History, Pencil, Plus, Target, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../app/providers";
import { clampProgress } from "../components/budgets/budgetPresentation";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { FinancialGoal, GoalMovement } from "../types";
import { formatCurrency, formatDate } from "../utils/formatters";

const today = () => new Date().toISOString().slice(0, 10);

export function GoalsPage() {
  const { user } = useAuth();
  const [goals, setGoals] = useState<FinancialGoal[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editor, setEditor] = useState<FinancialGoal | "new" | null>(null);
  const [moving, setMoving] = useState<FinancialGoal | null>(null);
  const [historyGoal, setHistoryGoal] = useState<FinancialGoal | null>(null);
  const [movements, setMovements] = useState<GoalMovement[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [target, setTarget] = useState("");
  const [deadline, setDeadline] = useState("");
  const [movementType, setMovementType] = useState<"contribution" | "withdrawal">("contribution");
  const [amount, setAmount] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(today);
  const [movementDescription, setMovementDescription] = useState("");

  async function load() {
    if (!user) return;
    try { setLoading(true); setGoals(await api.getGoals()); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar as metas."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [user?.id]);

  function openEditor(goal: FinancialGoal | "new") {
    setEditor(goal); setName(goal === "new" ? "" : goal.name); setDescription(goal === "new" ? "" : goal.description ?? "");
    setTarget(goal === "new" ? "" : goal.target_amount); setDeadline(goal === "new" ? "" : goal.deadline ?? "");
  }
  async function submitGoal(event: FormEvent) {
    event.preventDefault();
    try {
      setSaving(true);
      const payload = { name, description: description || null, target_amount: target, deadline: deadline || null };
      if (editor === "new") await api.createGoal(payload); else if (editor) await api.updateGoal(editor.id, payload);
      setEditor(null); setMessage(editor === "new" ? "Meta criada." : "Meta atualizada."); setError(""); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível salvar a meta."); }
    finally { setSaving(false); }
  }
  function openMovement(goal: FinancialGoal) { setMoving(goal); setMovementType("contribution"); setAmount(""); setEffectiveDate(today()); setMovementDescription(""); }
  async function submitMovement(event: FormEvent) {
    event.preventDefault(); if (!moving) return;
    try {
      setSaving(true);
      await api.addGoalMovement(moving.id, { type: movementType, amount, effective_date: effectiveDate, description: movementDescription || null, idempotency_key: crypto.randomUUID() });
      setMoving(null); setMessage(movementType === "contribution" ? "Aporte registrado." : "Retirada registrada."); setError(""); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível registrar a movimentação."); }
    finally { setSaving(false); }
  }
  async function openHistory(goal: FinancialGoal) {
    try { setMovements(await api.getGoalMovements(goal.id)); setHistoryGoal(goal); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar o histórico."); }
  }
  async function archiveOrDelete(goal: FinancialGoal) {
    if (!window.confirm(`Remover a meta “${goal.name}”? Metas com histórico serão arquivadas.`)) return;
    try { const result = await api.deleteGoal(goal.id); setMessage(result.outcome === "archived" ? "Meta arquivada e histórico preservado." : "Meta excluída."); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível remover a meta."); }
  }
  async function reactivate(goal: FinancialGoal) { try { await api.updateGoal(goal.id, { lifecycle_status: "active" }); setMessage("Meta reativada."); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível reativar a meta."); } }

  return <div className="page-stack">
    <PageHeader action={<Button onClick={() => openEditor("new")} type="button"><Plus size={18} />Nova meta</Button>} description="Acompanhe valores reservados de forma lógica, sem alterar saldos bancários." eyebrow="Planejamento" title="Metas financeiras" />
    {error ? <Feedback>{error}</Feedback> : null}{message ? <Feedback tone="success">{message}</Feedback> : null}
    <section aria-busy={loading} aria-label="Metas financeiras" className="goal-grid">
      {loading ? [1,2,3].map(item => <span className="surface-card skeleton goal-card-skeleton" key={item} />) : null}
      {!loading && goals.length === 0 ? <Card className="goal-empty-card"><EmptyState action={<Button onClick={() => openEditor("new")} type="button"><Plus size={18} />Criar meta</Button>} description="Crie uma meta e registre aportes virtuais para acompanhar seu progresso." icon={Target} title="Nenhuma meta criada" /></Card> : null}
      {!loading && goals.map(goal => { const percentage=Number(goal.progress_percentage); return <Card className={`goal-card ${goal.lifecycle_status === "archived" ? "goal-card-archived" : ""}`} key={goal.id}>
        <div className="goal-heading"><span className="goal-icon"><Target size={19}/></span><div><h2>{goal.name}</h2><small>{goal.completed ? "Meta atingida" : goal.lifecycle_status === "archived" ? "Arquivada" : "Em andamento"}</small></div></div>
        {goal.description ? <p className="goal-description">{goal.description}</p> : null}
        <div className="goal-values"><strong>{formatCurrency(Number(goal.saved_amount))}</strong><span>de {formatCurrency(Number(goal.target_amount))}</span><b>{percentage.toLocaleString("pt-BR", {maximumFractionDigits:2})}%</b></div>
        <div aria-label={`${percentage}% da meta alcançada`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={clampProgress(percentage)} className="goal-progress" role="progressbar"><i style={{width:`${clampProgress(percentage)}%`}} /></div>
        <div className="goal-meta"><span>{goal.remaining_amount === "0.00" ? "Objetivo alcançado" : `${formatCurrency(Number(goal.remaining_amount))} restantes`}</span>{goal.deadline ? <span><CalendarDays size={14}/>{formatDate(goal.deadline)}</span> : <span>Sem prazo</span>}</div>
        <div className="goal-actions"><Button onClick={() => void openHistory(goal)} type="button" variant="ghost"><History size={16}/>Histórico</Button>{goal.lifecycle_status === "active" ? <><Button onClick={() => openMovement(goal)} type="button" variant="secondary"><TrendingUp size={16}/>Movimentar</Button><button aria-label={`Editar ${goal.name}`} className="icon-button" onClick={() => openEditor(goal)} type="button"><Pencil size={16}/></button><button aria-label={`Arquivar ou excluir ${goal.name}`} className="icon-button icon-button-danger" onClick={() => void archiveOrDelete(goal)} type="button"><Archive size={16}/></button></> : <Button onClick={() => void reactivate(goal)} type="button" variant="secondary">Reativar</Button>}</div>
      </Card>; })}
    </section>
    {editor ? <Modal onClose={() => setEditor(null)} title={editor === "new" ? "Nova meta" : "Editar meta"}><form className="form-grid" onSubmit={submitGoal}><label>Nome<input autoFocus maxLength={120} onChange={e=>setName(e.target.value)} required value={name}/></label><label>Descrição opcional<textarea maxLength={600} onChange={e=>setDescription(e.target.value)} value={description}/></label><label>Valor-alvo<input inputMode="decimal" min="0.01" onChange={e=>setTarget(e.target.value)} required step="0.01" type="number" value={target}/></label><label>Data-limite opcional<input onChange={e=>setDeadline(e.target.value)} type="date" value={deadline}/></label><small className="field-hint">O valor reservado é lógico e não altera saldos ou transações.</small><Button disabled={saving || !name.trim() || Number(target)<=0} type="submit">{saving?"Salvando...":"Salvar meta"}</Button></form></Modal> : null}
    {moving ? <Modal onClose={() => setMoving(null)} title={`Movimentar ${moving.name}`}><form className="form-grid" onSubmit={submitMovement}><label>Tipo<select onChange={e=>setMovementType(e.target.value as typeof movementType)} value={movementType}><option value="contribution">Aporte</option><option value="withdrawal">Retirada</option></select></label><label>Valor<input autoFocus inputMode="decimal" min="0.01" onChange={e=>setAmount(e.target.value)} required step="0.01" type="number" value={amount}/></label><label>Data efetiva<input onChange={e=>setEffectiveDate(e.target.value)} required type="date" value={effectiveDate}/></label><label>Descrição opcional<input maxLength={300} onChange={e=>setMovementDescription(e.target.value)} value={movementDescription}/></label><small className="field-hint">Esta reserva virtual não movimenta sua conta bancária.</small><Button disabled={saving || Number(amount)<=0} type="submit">{saving?"Registrando...":movementType==="contribution"?"Registrar aporte":"Registrar retirada"}</Button></form></Modal> : null}
    {historyGoal ? <Modal onClose={() => setHistoryGoal(null)} title={`Histórico de ${historyGoal.name}`}><div className="goal-history">{movements.length===0?<EmptyState description="Aportes e retiradas aparecerão aqui." icon={History} title="Sem movimentações"/>:movements.map(m=><div className="goal-movement" key={m.id}><span className={m.type}>{m.type==="contribution"?<TrendingUp size={17}/>:<TrendingDown size={17}/>}</span><div><strong>{m.type==="contribution"?"Aporte":"Retirada"}</strong><small>{m.description||"Reserva lógica"} · {formatDate(m.effective_date)}{!m.effective?" · futura":""}</small></div><b>{m.type==="contribution"?"+":"−"}{formatCurrency(Number(m.amount))}</b></div>)}</div></Modal> : null}
  </div>;
}
