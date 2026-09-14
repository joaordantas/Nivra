import { ArrowDownLeft, ArrowRight, ArrowUpRight, CheckCircle2, CircleDollarSign, Plus, ReceiptText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../app/providers";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Account, ProfitSummary, Transaction } from "../types";
import { formatCurrency, formatDate, getCurrentMonthRange } from "../utils/formatters";

export function DashboardPage() {
  const { user } = useAuth();
  const period = useMemo(getCurrentMonthRange, []);
  const [profit, setProfit] = useState<ProfitSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    async function loadDashboard() {
      try {
        setLoading(true);
        setError("");
        setProfit(null);
        setTransactions(null);
        setAccounts(null);

        const [profitResult, transactionResult, accountResult] = await Promise.allSettled([
          api.getProfit(period.start, period.end),
          api.getTransactions(undefined, new Date().toISOString().slice(0, 10)),
          api.getAccounts(),
        ]);

        if (profitResult.status === "fulfilled") setProfit(profitResult.value);
        if (transactionResult.status === "fulfilled") setTransactions(transactionResult.value.slice(0, 5));
        if (accountResult.status === "fulfilled") setAccounts(accountResult.value);

        if ([profitResult, transactionResult, accountResult].some((result) => result.status === "rejected")) {
          setError("Não foi possível carregar parte do seu resumo financeiro.");
        }
      } catch {
        setError("Não foi possível carregar seu resumo financeiro.");
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [period.end, period.start, user]);

  const firstName = user?.usuario.split(" ")[0] ?? "";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const totalBalance = accounts?.reduce((total, account) => total + account.saldo_atual, 0) ?? 0;
  const bankAccounts = accounts?.filter((account) => account.origem === "open_finance") ?? [];
  const bankSyncDates = bankAccounts
    .map((account) => account.ultima_sincronizacao_em)
    .filter((value): value is string => Boolean(value))
    .sort();
  const latestBankSync = bankSyncDates[bankSyncDates.length - 1];
  let attentionTitle = "Resumo parcialmente indisponível";
  let attentionDescription = "Os dados que foram carregados continuam disponíveis enquanto tentamos recuperar o restante.";
  if (profit !== null && transactions !== null) {
    if (transactions.length === 0) {
      attentionTitle = "Tudo pronto para começar";
      attentionDescription = "Registre uma movimentação para começar a acompanhar seu mês.";
    } else if (profit.lucro >= 0) {
      attentionTitle = "Seu mês está positivo";
      attentionDescription = `Você mantém ${formatCurrency(profit.lucro)} depois dos gastos registrados.`;
    } else {
      attentionTitle = "Seus gastos passaram das entradas";
      attentionDescription = `A diferença atual é de ${formatCurrency(Math.abs(profit.lucro))}.`;
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        action={<Link className="button button-primary" to="/transactions?new=1#new-transaction"><Plus size={18} />Nova transação</Link>}
        description="Veja o que importa nas suas finanças agora."
        eyebrow={period.label}
        title={`${greeting}, ${firstName}`}
      />

      {error ? <Feedback>{error}</Feedback> : null}

      <Card className="balance-card">
        <div>
          <span className="card-label">Saldo registrado</span>
          {loading ? <span className="skeleton skeleton-value" /> : <strong>{accounts === null ? "—" : formatCurrency(totalBalance)}</strong>}
          <small>{accounts === null ? "Não foi possível carregar este valor." : accounts.length ? `Somado entre ${accounts.length} ${accounts.length === 1 ? "conta" : "contas"}${bankAccounts.length ? ` · ${bankAccounts.length} ${bankAccounts.length === 1 ? "saldo bancário" : "saldos bancários"}${latestBankSync ? ` atualizados em ${new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(latestBankSync))}` : ""}` : ""}` : "Adicione uma conta ou conecte um banco de demonstração em Contas."}</small>
        </div>
        <span className="balance-icon"><CircleDollarSign aria-hidden="true" size={26} /></span>
      </Card>

      <section aria-label="Resumo do mês" className="summary-grid">
        <Card className="summary-card">
          <span className="summary-icon income"><ArrowDownLeft size={18} /></span>
          <span>Entradas</span>
          {loading ? <span className="skeleton skeleton-line" /> : <strong>{profit === null ? "—" : formatCurrency(profit.entrada)}</strong>}
        </Card>
        <Card className="summary-card">
          <span className="summary-icon expense"><ArrowUpRight size={18} /></span>
          <span>Gastos</span>
          {loading ? <span className="skeleton skeleton-line" /> : <strong>{profit === null ? "—" : formatCurrency(profit.saida)}</strong>}
        </Card>
        <Card className="summary-card">
          <span className="summary-icon savings"><CircleDollarSign size={18} /></span>
          <span>Economizado</span>
          {loading ? <span className="skeleton skeleton-line" /> : <strong>{profit === null ? "—" : formatCurrency(Math.max(profit.lucro, 0))}</strong>}
        </Card>
      </section>

      <div className="dashboard-grid">
        <Card className="attention-card">
          <div className="card-heading">
            <div>
              <span className="section-kicker">Sua atenção</span>
              <h2>O que merece atenção</h2>
            </div>
          </div>
          <div className="attention-item attention-positive">
            <span><CheckCircle2 aria-hidden="true" size={20} /></span>
            <div>
              <strong>{attentionTitle}</strong>
              <p>{attentionDescription}</p>
            </div>
          </div>
          <p className="attention-note">Novos alertas aparecerão aqui conforme orçamentos, contas e cartões forem adicionados.</p>
        </Card>

        <Card className="recent-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Movimentações</span>
              <h2>Transações recentes</h2>
            </div>
            <Link className="text-link" to="/transactions">Ver todas <ArrowRight size={16} /></Link>
          </div>

          {loading ? (
            <div className="transaction-list" aria-label="Carregando transações">
              {[1, 2, 3].map((item) => <span className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : transactions === null ? (
            <p className="section-unavailable">Não foi possível carregar as transações recentes.</p>
          ) : transactions.length === 0 ? (
            <EmptyState
              action={<Link className="button button-secondary" to="/accounts">Conectar banco de demonstração</Link>}
              description="Conecte um banco de demonstração ou adicione sua primeira movimentação para começar a acompanhar suas finanças."
              icon={ReceiptText}
              title="Nenhuma transação ainda"
            />
          ) : (
            <div className="transaction-list">
              {transactions.map((transaction) => {
                const isIncome = transaction.tipo === "entrada";
                return (
                  <div className="transaction-row" key={`${transaction.origem}-${transaction.id}`}>
                    <span className={`transaction-icon ${isIncome ? "income" : "expense"}`}>
                      {isIncome ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}
                    </span>
                    <span className="transaction-info">
                      <span className="transaction-title-line"><strong>{transaction.comentario || transaction.categoria || (isIncome ? "Receita" : "Despesa")}</strong>{transaction.numero_parcela && transaction.quantidade_parcelas ? <span className="installment-badge static">{transaction.numero_parcela}/{transaction.quantidade_parcelas}</span> : null}</span>
                      <small>{transaction.categoria || "Sem categoria"} · {transaction.conta} · {formatDate(transaction.data)}</small>
                      <span className="transaction-origin-line"><span className={`transaction-origin ${transaction.conciliada_com_banco ? "reconciled" : transaction.origem === "open_finance" ? "bank" : "manual"}`}>{transaction.conciliada_com_banco ? "Manual + Banco" : transaction.origem === "open_finance" ? "Banco" : "Manual"}</span>{transaction.neutra ? <span className="transaction-origin neutral">Transferência interna</span> : null}</span>
                    </span>
                    <strong className={isIncome ? "amount-income" : "amount-expense"}>
                      {isIncome ? "+" : "−"} {formatCurrency(transaction.valor)}
                    </strong>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
