import { ArrowDownLeft, ArrowRightLeft, ArrowUpRight, Check, FilterX, Landmark, Pencil, ReceiptText, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../app/providers";
import { InstallmentPlans } from "../components/finance/InstallmentPlans";
import { MovementForm } from "../components/finance/MovementForm";
import { ReconciliationReview } from "../components/finance/ReconciliationReview";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Account, Category, MovementFormValues, MovementType, Transaction, TransactionSummary, Transfer } from "../types";
import { formatCurrency, formatDate } from "../utils/formatters";

type Movement =
  | { kind: "transaction"; id: number; tipo: "entrada" | "saida"; valor: number; descricao: string; data: string; categoriaId: number | null; categoria: string; contaId: number | null; conta: string; origem: "manual" | "open_finance"; editavel: boolean; statusConciliacao: Transaction["status_conciliacao"]; conciliadaComBanco: boolean; neutra: boolean; instituicaoNome: string | null; parcelamentoId: number | null; numeroParcela: number | null; quantidadeParcelas: number | null }
  | { kind: "transfer"; id: number; tipo: "transferencia"; valor: number; descricao: string; data: string; contaOrigemId: number; contaOrigem: string; contaDestinoId: number; contaDestino: string };

type TypeFilter = "todos" | MovementType;
type OriginFilter = "todas" | "manual" | "open_finance" | "conciliada";
const PAGE_SIZE = 25;

function initialForm(accounts: Account[]): MovementFormValues {
  const defaultAccount = accounts.find((account) => account.principal) ?? accounts[0];
  const secondAccount = accounts.find((account) => account.id !== defaultAccount?.id);
  return {
    tipo: "saida",
    valor: 0,
    descricao: "",
    data: new Date().toISOString().slice(0, 10),
    categoriaId: null,
    contaId: defaultAccount?.id ?? null,
    contaOrigemId: defaultAccount?.id ?? 0,
    contaDestinoId: secondAccount?.id ?? 0,
    forma: "avista",
    quantidadeParcelas: 2,
  };
}

function movementFormValues(movement: Movement): MovementFormValues {
  if (movement.kind === "transfer") {
    return {
      tipo: "transferencia",
      valor: movement.valor,
      descricao: movement.descricao,
      data: movement.data,
      categoriaId: null,
      contaId: null,
      contaOrigemId: movement.contaOrigemId,
      contaDestinoId: movement.contaDestinoId,
      forma: "avista",
      quantidadeParcelas: 2,
    };
  }
  return {
    tipo: movement.tipo,
    valor: movement.valor,
    descricao: movement.descricao,
    data: movement.data,
    categoriaId: movement.categoriaId,
    contaId: movement.contaId,
    contaOrigemId: 0,
    contaDestinoId: 0,
    forma: "avista",
    quantidadeParcelas: 2,
  };
}

export function TransactionsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const formRef = useRef<HTMLElement>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formVersion, setFormVersion] = useState(0);
  const [editing, setEditing] = useState<Movement | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("todos");
  const [accountFilter, setAccountFilter] = useState(0);
  const [categoryFilter, setCategoryFilter] = useState(0);
  const [originFilter, setOriginFilter] = useState<OriginFilter>("todas");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [summary, setSummary] = useState<TransactionSummary>({ entradas: 0, saidas: 0, saldo: 0 });
  const [selectedInstallmentPlanId, setSelectedInstallmentPlanId] = useState<number | null>(null);

  const movements = useMemo<Movement[]>(() => [
    ...transactions.map((transaction): Movement => ({
      kind: "transaction",
      id: transaction.id,
      tipo: transaction.tipo,
      valor: transaction.valor,
      descricao: transaction.comentario ?? "",
      data: transaction.data,
      categoriaId: transaction.categoria_id,
      categoria: transaction.categoria,
      contaId: transaction.conta_id,
      conta: transaction.conta,
      origem: transaction.origem,
      editavel: transaction.editavel,
      statusConciliacao: transaction.status_conciliacao,
      conciliadaComBanco: transaction.conciliada_com_banco,
      neutra: transaction.neutra,
      instituicaoNome: transaction.instituicao_nome,
      parcelamentoId: transaction.parcelamento_id,
      numeroParcela: transaction.numero_parcela,
      quantidadeParcelas: transaction.quantidade_parcelas,
    })),
    ...transfers.map((transfer): Movement => ({
      kind: "transfer",
      id: transfer.id,
      tipo: "transferencia",
      valor: transfer.valor,
      descricao: transfer.descricao ?? "",
      data: transfer.data,
      contaOrigemId: transfer.conta_origem_id,
      contaOrigem: transfer.conta_origem,
      contaDestinoId: transfer.conta_destino_id,
      contaDestino: transfer.conta_destino,
    })),
  ].sort((a, b) => b.data.localeCompare(a.data) || b.id - a.id), [transactions, transfers]);

  const filteredMovements = movements;

  const hasFilters = Boolean(search || typeFilter !== "todos" || accountFilter || categoryFilter || originFilter !== "todas" || startDate || endDate);

  async function load(targetPage = page) {
    if (!user) return;
    try {
      setLoading(true);
      const [movementPage, categoryData, accountData] = await Promise.all([
        api.getMovementPage({
          search,
          movementType: typeFilter === "todos" ? undefined : typeFilter,
          accountId: accountFilter || undefined,
          categoryId: categoryFilter || undefined,
          origin: originFilter === "todas" ? undefined : originFilter,
          startDate,
          endDate,
          limit: PAGE_SIZE,
          offset: targetPage * PAGE_SIZE,
        }),
        api.getCategories(),
        api.getAccounts(),
      ]);
      setTransactions(movementPage.items.filter((item) => item.kind === "transaction").map((item) => item.transaction));
      setTransfers(movementPage.items.filter((item) => item.kind === "transfer").map((item) => item.transfer));
      setCategories(categoryData);
      setAccounts(accountData);
      setTotal(movementPage.total);
      setHasMore(movementPage.has_more);
      setSummary(movementPage.summary);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar suas movimentações.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(page); }, search ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [user?.id, page, search, typeFilter, accountFilter, categoryFilter, originFilter, startDate, endDate]);

  useEffect(() => {
    if (searchParams.get("new") === "1") {
      window.requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  }, [searchParams]);

  async function createCategory(name: string) {
    if (!user) throw new Error("Sessão inválida.");
    const category = await api.createCategory(name);
    setCategories((current) => [...current, category].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")));
    return category;
  }

  async function createMovement(values: MovementFormValues) {
    if (!user) return;
    try {
      setSaving(true);
      if (values.tipo === "transferencia") {
        await api.createTransfer({ conta_origem_id: values.contaOrigemId, conta_destino_id: values.contaDestinoId, valor: values.valor, descricao: values.descricao, data: values.data });
      } else if (values.forma === "parcelado") {
        await api.createInstallmentPlan({
          descricao: values.descricao,
          valor_total: values.valor,
          quantidade_parcelas: values.quantidadeParcelas,
          data_inicial: values.data,
          tipo: values.tipo,
          categoria_id: values.categoriaId,
          conta_id: values.contaId,
        });
      } else {
        await api.createTransaction({ valor: values.valor, tipo: values.tipo, categoria_id: values.categoriaId, comentario: values.descricao, data: values.data, conta_id: values.contaId });
      }
      setFormVersion((current) => current + 1);
      setMessage(values.tipo === "transferencia" ? "Transferência registrada sem alterar receitas e despesas." : values.forma === "parcelado" ? "Parcelamento criado com todas as parcelas." : "Movimentação adicionada com sucesso.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar a movimentação.");
      setMessage("");
    } finally {
      setSaving(false);
    }
  }

  async function updateMovement(values: MovementFormValues) {
    if (!user || !editing) return;
    try {
      setSaving(true);
      if (editing.kind === "transfer") {
        await api.updateTransfer(editing.id, { conta_origem_id: values.contaOrigemId, conta_destino_id: values.contaDestinoId, valor: values.valor, descricao: values.descricao, data: values.data });
      } else if (values.tipo !== "transferencia") {
        await api.updateTransaction(editing.id, { valor: values.valor, tipo: values.tipo, categoria_id: values.categoriaId, comentario: values.descricao, data: values.data, conta_id: values.contaId });
      }
      setEditing(null);
      setMessage("Movimentação atualizada com sucesso.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar a movimentação.");
      setMessage("");
    } finally {
      setSaving(false);
    }
  }

  async function deleteMovement(movement: Movement) {
    if (!user || !window.confirm(`Excluir \"${movement.descricao || "movimentação"}\"?`)) return;
    try {
      if (movement.kind === "transfer") await api.deleteTransfer(movement.id);
      else await api.deleteTransaction(movement.id);
      setMessage("Movimentação excluída e saldos recalculados.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível excluir a movimentação.");
      setMessage("");
    }
  }

  function clearFilters() {
    setSearch("");
    setTypeFilter("todos");
    setAccountFilter(0);
    setCategoryFilter(0);
    setOriginFilter("todas");
    setStartDate("");
    setEndDate("");
    setPage(0);
  }

  return (
    <div className="page-stack">
      <PageHeader description="Registre, encontre e corrija todas as suas movimentações." eyebrow="Organização financeira" title="Transações" />
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}

      <section className="summary-grid compact-summary" aria-label="Resumo dos resultados exibidos">
        <Card className="summary-card"><span>Resultado exibido</span><strong>{formatCurrency(summary.saldo)}</strong></Card>
        <Card className="summary-card"><span>Entradas</span><strong className="amount-income">{formatCurrency(summary.entradas)}</strong></Card>
        <Card className="summary-card"><span>Gastos</span><strong>{formatCurrency(summary.saidas)}</strong></Card>
      </section>

      <ReconciliationReview onChanged={load} />

      <div className="transactions-layout">
        <section id="new-transaction" ref={formRef}>
          <Card className="transaction-form-card">
            <div className="card-heading"><span className="section-kicker">Registro rápido</span><h2>Nova movimentação</h2></div>
            <MovementForm accounts={accounts} autoFocus={searchParams.get("new") === "1"} categories={categories} initialValues={initialForm(accounts)} key={`create-${formVersion}-${accounts.map((account) => account.id).join("-")}`} mode="create" onCreateCategory={createCategory} onSubmit={createMovement} saving={saving} />
          </Card>
        </section>

        <Card as="section" className="transactions-history">
          <div className="card-heading card-heading-row"><div><span className="section-kicker">Histórico unificado</span><h2>Suas movimentações</h2></div><span className="count-badge">{total}</span></div>
          <div className="transaction-filters transaction-filters-full">
            <label className="search-field"><Search aria-hidden="true" size={17} /><input aria-label="Buscar movimentações" onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="Buscar descrição, categoria ou conta" value={search} /></label>
            <select aria-label="Filtrar por tipo" onChange={(event) => { setTypeFilter(event.target.value as TypeFilter); setPage(0); }} value={typeFilter}><option value="todos">Todos os tipos</option><option value="saida">Despesas</option><option value="entrada">Receitas</option><option value="transferencia">Transferências</option></select>
            <select aria-label="Filtrar por conta" onChange={(event) => { setAccountFilter(Number(event.target.value)); setPage(0); }} value={accountFilter}><option value={0}>Todas as contas</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.nome}</option>)}</select>
            <select aria-label="Filtrar por categoria" onChange={(event) => { setCategoryFilter(Number(event.target.value)); setPage(0); }} value={categoryFilter}><option value={0}>Todas as categorias</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.nome}</option>)}</select>
            <select aria-label="Filtrar por origem" onChange={(event) => { setOriginFilter(event.target.value as OriginFilter); setPage(0); }} value={originFilter}><option value="todas">Todas as origens</option><option value="manual">Manual</option><option value="open_finance">Banco</option><option value="conciliada">Manual + Banco</option></select>
            <label className="filter-date"><span>De</span><input aria-label="Data inicial" onChange={(event) => { setStartDate(event.target.value); setPage(0); }} type="date" value={startDate} /></label>
            <label className="filter-date"><span>Até</span><input aria-label="Data final" min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setPage(0); }} type="date" value={endDate} /></label>
          </div>
          {hasFilters ? <button className="text-button clear-filters" onClick={clearFilters} type="button"><FilterX size={15} />Limpar filtros</button> : null}

          {loading ? (
            <div className="transaction-list">{[1, 2, 3, 4].map((item) => <span className="skeleton skeleton-row" key={item} />)}</div>
          ) : filteredMovements.length === 0 ? (
            <EmptyState description={!hasFilters ? "Suas movimentações aparecerão aqui. Você pode registrar uma agora ou conectar um banco de demonstração em Contas." : "Ajuste ou limpe os filtros para ver outros resultados."} icon={ReceiptText} title={!hasFilters ? "Nenhuma movimentação registrada" : "Nenhum resultado encontrado"} />
          ) : (
            <div className="transaction-list">
              {filteredMovements.map((movement) => {
                const isIncome = movement.tipo === "entrada";
                const isTransfer = movement.kind === "transfer";
                return (
                  <div className="transaction-row transaction-row-actions" key={`${movement.kind}-${movement.kind === "transaction" ? movement.origem : "manual"}-${movement.id}`}>
                    <span className={`transaction-icon ${isTransfer ? "transfer" : isIncome ? "income" : "expense"}`}>{isTransfer ? <ArrowRightLeft size={18} /> : isIncome ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}</span>
                    <span className="transaction-info"><span className="transaction-title-line"><strong>{movement.descricao || (isTransfer ? "Transferência" : isIncome ? "Receita" : "Despesa")}</strong>{movement.kind === "transaction" && movement.parcelamentoId && movement.numeroParcela && movement.quantidadeParcelas ? <button className="installment-badge" onClick={() => setSelectedInstallmentPlanId(movement.parcelamentoId)} type="button">{movement.numeroParcela}/{movement.quantidadeParcelas}</button> : null}</span><small>{isTransfer ? `${movement.contaOrigem} → ${movement.contaDestino}` : `${movement.categoria || "Sem categoria"} · ${movement.conta}`} · {formatDate(movement.data)}</small>{movement.kind === "transaction" ? <span className="transaction-origin-line"><span className={`transaction-origin ${movement.conciliadaComBanco ? "reconciled" : movement.origem === "open_finance" ? "bank" : "manual"}`}>{movement.conciliadaComBanco ? <><Check size={12} />Manual + Banco</> : movement.origem === "open_finance" ? <><Landmark size={12} />Banco</> : "Manual"}</span>{movement.data > new Date().toISOString().slice(0, 10) ? <span className="transaction-origin future">Futura</span> : null}{movement.statusConciliacao === "possivel_correspondencia" || movement.statusConciliacao === "ambigua" ? <span className="transaction-origin possible">{movement.statusConciliacao === "ambigua" ? "Mais de uma correspondência" : "Possível correspondência"}</span> : null}{movement.neutra ? <span className="transaction-origin neutral">Transferência interna</span> : null}{movement.instituicaoNome ? <small>{movement.instituicaoNome}</small> : null}</span> : null}</span>
                    <strong className={isIncome ? "amount-income" : isTransfer ? "" : "amount-expense"}>{isIncome ? "+" : isTransfer ? "" : "−"} {formatCurrency(movement.valor)}</strong>
                    {movement.kind === "transfer" || movement.editavel ? <span className="movement-actions"><button aria-label={`Editar ${movement.descricao || "movimentação"}`} className="icon-button" onClick={() => setEditing(movement)} type="button"><Pencil size={15} /></button><button aria-label={`Excluir ${movement.descricao || "movimentação"}`} className="icon-button danger-icon-button" onClick={() => void deleteMovement(movement)} type="button"><Trash2 size={15} /></button></span> : null}
                  </div>
                );
              })}
            </div>
          )}
          {!loading && total > 0 ? <nav aria-label="Paginação das movimentações" className="pagination-controls"><span>Página {page + 1} de {Math.max(1, Math.ceil(total / PAGE_SIZE))} · {total} resultados</span><div><Button disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))} type="button" variant="secondary">Anterior</Button><Button disabled={!hasMore} onClick={() => setPage((current) => current + 1)} type="button" variant="secondary">Próxima</Button></div></nav> : null}
        </Card>
      </div>

      <InstallmentPlans accounts={accounts} categories={categories} onChanged={load} onSelectPlan={setSelectedInstallmentPlanId} refreshKey={formVersion} selectedPlanId={selectedInstallmentPlanId} />

      {editing ? <Modal onClose={() => setEditing(null)} title="Editar movimentação"><MovementForm accounts={accounts} categories={categories} initialValues={movementFormValues(editing)} key={`${editing.kind}-${editing.id}`} mode="edit" onCreateCategory={createCategory} onSubmit={updateMovement} saving={saving} /></Modal> : null}
    </div>
  );
}
