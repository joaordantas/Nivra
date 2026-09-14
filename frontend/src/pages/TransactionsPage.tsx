import { ArrowDownLeft, ArrowRightLeft, ArrowUpRight, Check, FilterX, Landmark, Pencil, ReceiptText, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../app/providers";
import { MovementForm } from "../components/finance/MovementForm";
import { ReconciliationReview } from "../components/finance/ReconciliationReview";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Account, Category, MovementFormValues, MovementType, Transaction, Transfer } from "../types";
import { formatCurrency, formatDate } from "../utils/formatters";

type Movement =
  | { kind: "transaction"; id: number; tipo: "entrada" | "saida"; valor: number; descricao: string; data: string; categoriaId: number | null; categoria: string; contaId: number | null; conta: string; origem: "manual" | "open_finance"; editavel: boolean; statusConciliacao: Transaction["status_conciliacao"]; conciliadaComBanco: boolean; neutra: boolean; instituicaoNome: string | null }
  | { kind: "transfer"; id: number; tipo: "transferencia"; valor: number; descricao: string; data: string; contaOrigemId: number; contaOrigem: string; contaDestinoId: number; contaDestino: string };

type TypeFilter = "todos" | MovementType;
type OriginFilter = "todas" | "manual" | "open_finance" | "conciliada";

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

  const filteredMovements = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("pt-BR");
    return movements.filter((movement) => {
      const searchableValues = movement.kind === "transfer"
        ? [movement.descricao, movement.contaOrigem, movement.contaDestino]
        : [movement.descricao, movement.categoria, movement.conta];
      const matchesSearch = !normalizedSearch || searchableValues.some((value) => value.toLocaleLowerCase("pt-BR").includes(normalizedSearch));
      const matchesType = typeFilter === "todos" || movement.tipo === typeFilter;
      const matchesAccount = accountFilter === 0 || (movement.kind === "transfer"
        ? movement.contaOrigemId === accountFilter || movement.contaDestinoId === accountFilter
        : movement.contaId === accountFilter);
      const matchesCategory = categoryFilter === 0 || (movement.kind === "transaction" && movement.categoriaId === categoryFilter);
      const matchesOrigin = originFilter === "todas" || (originFilter === "manual"
        ? movement.kind === "transfer" || (movement.kind === "transaction" && movement.origem === "manual" && !movement.conciliadaComBanco)
        : movement.kind === "transaction" && (originFilter === "conciliada" ? movement.conciliadaComBanco : movement.origem === "open_finance"));
      const matchesStart = !startDate || movement.data >= startDate;
      const matchesEnd = !endDate || movement.data <= endDate;
      return matchesSearch && matchesType && matchesAccount && matchesCategory && matchesOrigin && matchesStart && matchesEnd;
    });
  }, [accountFilter, categoryFilter, endDate, movements, originFilter, search, startDate, typeFilter]);

  const summary = useMemo(() => filteredMovements.reduce((result, movement) => {
    if (movement.kind === "transaction" && movement.neutra) return result;
    if (movement.tipo === "entrada") result.entradas += movement.valor;
    if (movement.tipo === "saida") result.saidas += movement.valor;
    result.saldo = result.entradas - result.saidas;
    return result;
  }, { entradas: 0, saidas: 0, saldo: 0 }), [filteredMovements]);

  const hasFilters = Boolean(search || typeFilter !== "todos" || accountFilter || categoryFilter || originFilter !== "todas" || startDate || endDate);

  async function load() {
    if (!user) return;
    try {
      setLoading(true);
      const [transactionData, transferData, categoryData, accountData] = await Promise.all([
        api.getTransactions(),
        api.getTransfers(),
        api.getCategories(),
        api.getAccounts(),
      ]);
      setTransactions(transactionData);
      setTransfers(transferData);
      setCategories(categoryData);
      setAccounts(accountData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar suas movimentações.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [user?.id]);

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
      } else {
        await api.createTransaction({ valor: values.valor, tipo: values.tipo, categoria_id: values.categoriaId, comentario: values.descricao, data: values.data, conta_id: values.contaId });
      }
      setFormVersion((current) => current + 1);
      setMessage(values.tipo === "transferencia" ? "Transferência registrada sem alterar receitas e despesas." : "Movimentação adicionada com sucesso.");
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
            <MovementForm accounts={accounts} categories={categories} initialValues={initialForm(accounts)} key={`create-${formVersion}-${accounts.map((account) => account.id).join("-")}`} mode="create" onCreateCategory={createCategory} onSubmit={createMovement} saving={saving} />
          </Card>
        </section>

        <Card as="section" className="transactions-history">
          <div className="card-heading card-heading-row"><div><span className="section-kicker">Histórico unificado</span><h2>Suas movimentações</h2></div><span className="count-badge">{filteredMovements.length}</span></div>
          <div className="transaction-filters transaction-filters-full">
            <label className="search-field"><Search aria-hidden="true" size={17} /><input aria-label="Buscar movimentações" onChange={(event) => setSearch(event.target.value)} placeholder="Buscar descrição, categoria ou conta" value={search} /></label>
            <select aria-label="Filtrar por tipo" onChange={(event) => setTypeFilter(event.target.value as TypeFilter)} value={typeFilter}><option value="todos">Todos os tipos</option><option value="saida">Despesas</option><option value="entrada">Receitas</option><option value="transferencia">Transferências</option></select>
            <select aria-label="Filtrar por conta" onChange={(event) => setAccountFilter(Number(event.target.value))} value={accountFilter}><option value={0}>Todas as contas</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.nome}</option>)}</select>
            <select aria-label="Filtrar por categoria" onChange={(event) => setCategoryFilter(Number(event.target.value))} value={categoryFilter}><option value={0}>Todas as categorias</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.nome}</option>)}</select>
            <select aria-label="Filtrar por origem" onChange={(event) => setOriginFilter(event.target.value as OriginFilter)} value={originFilter}><option value="todas">Todas as origens</option><option value="manual">Manual</option><option value="open_finance">Banco</option><option value="conciliada">Manual + Banco</option></select>
            <label className="filter-date"><span>De</span><input aria-label="Data inicial" onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} /></label>
            <label className="filter-date"><span>Até</span><input aria-label="Data final" min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} /></label>
          </div>
          {hasFilters ? <button className="text-button clear-filters" onClick={clearFilters} type="button"><FilterX size={15} />Limpar filtros</button> : null}

          {loading ? (
            <div className="transaction-list">{[1, 2, 3, 4].map((item) => <span className="skeleton skeleton-row" key={item} />)}</div>
          ) : filteredMovements.length === 0 ? (
            <EmptyState description={movements.length === 0 ? "Suas movimentações aparecerão aqui. Você pode registrar uma agora ou conectar um banco de demonstração em Contas." : "Ajuste ou limpe os filtros para ver outros resultados."} icon={ReceiptText} title={movements.length === 0 ? "Nenhuma movimentação registrada" : "Nenhum resultado encontrado"} />
          ) : (
            <div className="transaction-list">
              {filteredMovements.map((movement) => {
                const isIncome = movement.tipo === "entrada";
                const isTransfer = movement.kind === "transfer";
                return (
                  <div className="transaction-row transaction-row-actions" key={`${movement.kind}-${movement.kind === "transaction" ? movement.origem : "manual"}-${movement.id}`}>
                    <span className={`transaction-icon ${isTransfer ? "transfer" : isIncome ? "income" : "expense"}`}>{isTransfer ? <ArrowRightLeft size={18} /> : isIncome ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}</span>
                    <span className="transaction-info"><strong>{movement.descricao || (isTransfer ? "Transferência" : isIncome ? "Receita" : "Despesa")}</strong><small>{isTransfer ? `${movement.contaOrigem} → ${movement.contaDestino}` : `${movement.categoria || "Sem categoria"} · ${movement.conta}`} · {formatDate(movement.data)}</small>{movement.kind === "transaction" ? <span className="transaction-origin-line"><span className={`transaction-origin ${movement.conciliadaComBanco ? "reconciled" : movement.origem === "open_finance" ? "bank" : "manual"}`}>{movement.conciliadaComBanco ? <><Check size={12} />Manual + Banco</> : movement.origem === "open_finance" ? <><Landmark size={12} />Banco</> : "Manual"}</span>{movement.statusConciliacao === "possivel_correspondencia" || movement.statusConciliacao === "ambigua" ? <span className="transaction-origin possible">{movement.statusConciliacao === "ambigua" ? "Mais de uma correspondência" : "Possível correspondência"}</span> : null}{movement.neutra ? <span className="transaction-origin neutral">Transferência interna</span> : null}{movement.instituicaoNome ? <small>{movement.instituicaoNome}</small> : null}</span> : null}</span>
                    <strong className={isIncome ? "amount-income" : isTransfer ? "" : "amount-expense"}>{isIncome ? "+" : isTransfer ? "" : "−"} {formatCurrency(movement.valor)}</strong>
                    {movement.kind === "transfer" || movement.editavel ? <span className="movement-actions"><button aria-label={`Editar ${movement.descricao || "movimentação"}`} className="icon-button" onClick={() => setEditing(movement)} type="button"><Pencil size={15} /></button><button aria-label={`Excluir ${movement.descricao || "movimentação"}`} className="icon-button danger-icon-button" onClick={() => void deleteMovement(movement)} type="button"><Trash2 size={15} /></button></span> : null}
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {editing ? <Modal onClose={() => setEditing(null)} title="Editar movimentação"><MovementForm accounts={accounts} categories={categories} initialValues={movementFormValues(editing)} key={`${editing.kind}-${editing.id}`} mode="edit" onCreateCategory={createCategory} onSubmit={updateMovement} saving={saving} /></Modal> : null}
    </div>
  );
}
