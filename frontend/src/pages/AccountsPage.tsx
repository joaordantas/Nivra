import { ArrowDownLeft, ArrowRight, ArrowRightLeft, Landmark, Pencil, Plus, Power, Star, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../app/providers";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { OpenFinanceConnectCard } from "../components/finance/OpenFinanceConnectCard";
import { api } from "../services/api";
import type { Account, AccountType, Transfer } from "../types";
import { formatCurrency, formatDate } from "../utils/formatters";

const accountTypeLabels: Record<AccountType, string> = {
  corrente: "Conta corrente",
  poupanca: "Poupança",
  digital: "Conta digital",
  dinheiro: "Dinheiro",
  outro: "Outra",
};

export function AccountsPage() {
  const { user } = useAuth();
  const today = new Date().toISOString().slice(0, 10);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("digital");
  const [initialBalance, setInitialBalance] = useState(0);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState<AccountType>("digital");
  const [editInitialBalance, setEditInitialBalance] = useState(0);
  const [sourceId, setSourceId] = useState(0);
  const [destinationId, setDestinationId] = useState(0);
  const [transferValue, setTransferValue] = useState(0);
  const [description, setDescription] = useState("");
  const [transferDate, setTransferDate] = useState(today);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const activeAccounts = useMemo(() => accounts.filter((account) => account.ativo), [accounts]);
  const totalBalance = useMemo(() => activeAccounts.reduce((total, account) => total + account.saldo_atual, 0), [activeAccounts]);

  async function load(preferredSourceId?: number) {
    if (!user) return;
    try {
      setLoading(true);
      const [accountData, transferData] = await Promise.all([api.getAccounts(true), api.getTransfers()]);
      setAccounts(accountData);
      setTransfers(transferData);
      const availableAccounts = accountData.filter((account) => account.ativo);
      const primaryAccount = availableAccounts.find((account) => account.principal);
      const defaultSourceId = primaryAccount?.id ?? availableAccounts[0]?.id ?? 0;
      const requestedSourceId = preferredSourceId ?? sourceId;
      const resolvedSourceId = availableAccounts.some((account) => account.id === requestedSourceId) ? requestedSourceId : defaultSourceId;
      setSourceId(resolvedSourceId);
      setDestinationId((current) => (
        availableAccounts.some((account) => account.id === current && account.id !== resolvedSourceId)
          ? current
          : availableAccounts.find((account) => account.id !== resolvedSourceId)?.id ?? 0
      ));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar suas contas.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [user?.id]);

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    try {
      setSaving(true);
      await api.createAccount({ nome: name, tipo: accountType, saldo_inicial: initialBalance });
      setName("");
      setInitialBalance(0);
      setMessage("Conta adicionada com sucesso.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível adicionar a conta.");
      setMessage("");
    } finally {
      setSaving(false);
    }
  }

  function openAccountEditor(account: Account) {
    setEditingAccount(account);
    setEditName(account.nome);
    setEditType(account.tipo);
    setEditInitialBalance(account.saldo_inicial);
  }

  async function handleEditAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || !editingAccount) return;
    try {
      setSaving(true);
      await api.updateAccount(editingAccount.id, { nome: editName, tipo: editType, saldo_inicial: editInitialBalance });
      setEditingAccount(null);
      setMessage("Conta atualizada e saldo recalculado.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar a conta.");
      setMessage("");
    } finally {
      setSaving(false);
    }
  }

  async function toggleAccount(account: Account) {
    if (!user) return;
    const action = account.ativo ? "desativar" : "reativar";
    if (!window.confirm(`${action[0].toUpperCase()}${action.slice(1)} a conta \"${account.nome}\"?`)) return;
    try {
      await api.updateAccountStatus(account.id, !account.ativo);
      setMessage(account.ativo ? "Conta desativada." : "Conta reativada.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Não foi possível ${action} a conta.`);
      setMessage("");
    }
  }

  async function setPrimaryAccount(account: Account) {
    if (!user || account.principal) return;
    try {
      await api.setPrimaryAccount(account.id);
      setMessage(`${account.nome} agora é sua conta principal.`);
      setError("");
      await load(account.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível definir a conta principal.");
      setMessage("");
    }
  }

  async function handleTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    try {
      setSaving(true);
      await api.createTransfer({ conta_origem_id: sourceId, conta_destino_id: destinationId, valor: transferValue, descricao: description, data: transferDate });
      setTransferValue(0);
      setDescription("");
      setMessage("Transferência registrada sem alterar suas receitas ou despesas.");
      setError("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível registrar a transferência.");
      setMessage("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader description="Acompanhe onde está seu dinheiro e mova valores entre contas." eyebrow="Patrimônio disponível" title="Contas" />
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}

      <Card className="accounts-total-card"><span>Saldo total nas contas ativas</span><strong>{loading ? "—" : formatCurrency(totalBalance)}</strong><small>Soma dos saldos atuais das suas contas</small></Card>

      <OpenFinanceConnectCard accounts={accounts} onAccountsChanged={() => load()} />

      <section className="account-cards" aria-label="Contas financeiras">
        {loading ? [1, 2].map((item) => <span className="surface-card skeleton account-card-skeleton" key={item} />) : null}
        {!loading && accounts.length === 0 ? <Card className="accounts-empty-card"><EmptyState description="Adicione onde seu dinheiro está para acompanhar o saldo corretamente." icon={Landmark} title="Você ainda não possui contas" /></Card> : null}
        {!loading && accounts.map((account) => (
          <Card className={`account-card ${account.ativo ? "" : "account-card-inactive"}`} key={account.id}>
            <span className="account-icon"><WalletCards aria-hidden="true" size={21} /></span>
            <div><small>{accountTypeLabels[account.tipo]}</small><h2>{account.nome}</h2></div>
            <span className="account-badges">
              {account.principal ? <span className="status-badge primary"><Star size={12} />Principal</span> : null}
              {account.origem === "open_finance" ? <span className="status-badge bank"><Landmark size={12} />Banco conectado</span> : null}
              <span className={`status-badge ${account.ativo ? "active" : "inactive"}`}>{account.ativo ? "Ativa" : "Inativa"}</span>
            </span>
            <strong>{formatCurrency(account.saldo_atual)}</strong>
            <span className="account-actions">
              {account.ativo && !account.principal ? <button aria-label={`Definir ${account.nome} como principal`} className="icon-button" onClick={() => void setPrimaryAccount(account)} title="Definir como principal" type="button"><Star size={15} /></button> : null}
              <button aria-label={`Editar ${account.nome}`} className="icon-button" onClick={() => openAccountEditor(account)} type="button"><Pencil size={15} /></button>
              <button aria-label={`${account.ativo ? "Desativar" : "Reativar"} ${account.nome}`} className="icon-button" onClick={() => void toggleAccount(account)} type="button"><Power size={15} /></button>
            </span>
            {account.percentual_uso > 0 ? <small className="account-usage">{account.percentual_uso.toLocaleString("pt-BR")}% das movimentações dos últimos 90 dias{account.mais_utilizada ? " · mais utilizada" : ""}</small> : null}
            {account.origem === "open_finance" ? <small className="account-source">Saldo atualizado pelo banco · {account.instituicao_nome ?? "Open Finance"}{account.ultima_sincronizacao_em ? ` · ${new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(account.ultima_sincronizacao_em))}` : ""}</small> : null}
          </Card>
        ))}
      </section>

      <div className="accounts-layout">
        <Card as="section" className="account-form-card">
          <div className="card-heading"><span className="section-kicker">Nova conta</span><h2>Onde está seu dinheiro?</h2></div>
          <form className="form-grid" onSubmit={handleCreateAccount}>
            <label>Nome<input maxLength={80} onChange={(event) => setName(event.target.value)} placeholder="Ex.: Nubank" value={name} /></label>
            <label>Tipo<select onChange={(event) => setAccountType(event.target.value as AccountType)} value={accountType}>{Object.entries(accountTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>Saldo atual<input onChange={(event) => setInitialBalance(Number(event.target.value))} step="0.01" type="number" value={initialBalance || ""} /></label>
            <Button disabled={saving || !name.trim()} type="submit"><Plus size={18} />Adicionar conta</Button>
          </form>
        </Card>

        <Card as="section" className="transfer-form-card">
          <div className="card-heading"><span className="section-kicker">Entre contas</span><h2>Nova transferência</h2></div>
          {activeAccounts.length < 2 ? (
            <div className="inline-empty"><ArrowRightLeft size={20} /><p>Adicione ou reative pelo menos duas contas para fazer uma transferência.</p></div>
          ) : (
            <form className="form-grid" onSubmit={handleTransfer}>
              <div className="transfer-accounts">
                <label>De<select onChange={(event) => setSourceId(Number(event.target.value))} value={sourceId}>{activeAccounts.map((account) => <option disabled={account.id === destinationId} key={account.id} value={account.id}>{account.nome}</option>)}</select></label>
                <ArrowRight aria-hidden="true" size={20} />
                <label>Para<select onChange={(event) => setDestinationId(Number(event.target.value))} value={destinationId}>{activeAccounts.map((account) => <option disabled={account.id === sourceId} key={account.id} value={account.id}>{account.nome}</option>)}</select></label>
              </div>
              <label>Valor<input min="0.01" onChange={(event) => setTransferValue(Number(event.target.value))} placeholder="R$ 0,00" step="0.01" type="number" value={transferValue || ""} /></label>
              <label>Descrição<input maxLength={255} onChange={(event) => setDescription(event.target.value)} placeholder="Ex.: Dinheiro para pagamentos" value={description} /></label>
              <label>Data<input onChange={(event) => setTransferDate(event.target.value)} type="date" value={transferDate} /></label>
              <Button disabled={saving || !description.trim() || transferValue <= 0 || sourceId === destinationId} type="submit"><ArrowRightLeft size={18} />Transferir</Button>
            </form>
          )}
        </Card>
      </div>

      <Card as="section" className="transfer-history-card">
        <div className="card-heading card-heading-row"><div><span className="section-kicker">Histórico</span><h2>Transferências recentes</h2></div><span className="count-badge">{transfers.length}</span></div>
        {transfers.length === 0 ? <EmptyState description="Transferências entre suas contas aparecerão aqui." icon={ArrowRightLeft} title="Nenhuma transferência registrada" /> : (
          <div className="transaction-list">{transfers.slice(0, 5).map((transfer) => <div className="transaction-row" key={transfer.id}><span className="transaction-icon transfer"><ArrowDownLeft size={18} /></span><span className="transaction-info"><strong>{transfer.conta_origem} → {transfer.conta_destino}</strong><small>{transfer.descricao || "Transferência"} · {formatDate(transfer.data)}</small></span><strong>{formatCurrency(transfer.valor)}</strong></div>)}</div>
        )}
      </Card>

      {editingAccount ? (
        <Modal onClose={() => setEditingAccount(null)} title="Editar conta">
          <form className="form-grid" onSubmit={handleEditAccount}>
            <label>Nome<input autoFocus maxLength={80} onChange={(event) => setEditName(event.target.value)} value={editName} /></label>
            <label>Tipo<select onChange={(event) => setEditType(event.target.value as AccountType)} value={editType}>{Object.entries(accountTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>Saldo inicial<input disabled={editingAccount.origem === "open_finance"} onChange={(event) => setEditInitialBalance(Number(event.target.value))} step="0.01" type="number" value={editInitialBalance} /></label>
            <small className="field-hint">{editingAccount.origem === "open_finance" ? "O saldo atual é informado pelo banco e atualizado pela sincronização." : "Alterar o saldo inicial recalcula o saldo atual mantendo as movimentações registradas."}</small>
            <Button disabled={saving || !editName.trim()} type="submit">{saving ? "Salvando..." : "Salvar alterações"}</Button>
          </form>
        </Modal>
      ) : null}
    </div>
  );
}
