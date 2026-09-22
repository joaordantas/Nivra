import { AlertTriangle, ArrowDownLeft, ArrowRight, ArrowUpRight, CalendarRange, CheckCircle2, CircleDollarSign, CreditCard, Info, ListOrdered, Plus, ReceiptText, Repeat2, ScanSearch, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../app/providers";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Feedback } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Account, FinancialInsights, InsightSeverity, ProfitSummary, Transaction } from "../types";
import { formatCurrency, formatDate, getCurrentMonthRange } from "../utils/formatters";

const frequencyLabels = {
  weekly: "Semanal",
  fortnightly: "Quinzenal",
  monthly: "Mensal",
  approximately_monthly: "Aproximadamente mensal",
  annual: "Anual",
} as const;

export function DashboardPage() {
  const { user } = useAuth();
  const period = useMemo(getCurrentMonthRange, []);
  const [profit, setProfit] = useState<ProfitSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [insights, setInsights] = useState<FinancialInsights | null>(null);
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
        setInsights(null);

        const [profitResult, transactionResult, accountResult, insightResult] = await Promise.allSettled([
          api.getProfit(period.start, period.end),
          api.getTransactions(undefined, new Date().toISOString().slice(0, 10)),
          api.getAccounts(),
          api.getInsights(period.start, period.monthEnd),
        ]);

        if (profitResult.status === "fulfilled") setProfit(profitResult.value);
        if (transactionResult.status === "fulfilled") setTransactions(transactionResult.value.slice(0, 5));
        if (accountResult.status === "fulfilled") setAccounts(accountResult.value);
        if (insightResult.status === "fulfilled") setInsights(insightResult.value);

        if ([profitResult, transactionResult, accountResult, insightResult].some((result) => result.status === "rejected")) {
          setError("Não foi possível carregar parte do seu resumo financeiro.");
        }
      } catch {
        setError("Não foi possível carregar seu resumo financeiro.");
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [period.end, period.monthEnd, period.start, user]);

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
  const recentTrendPoints = insights?.monthly_trend.points.slice(-4) ?? [];
  const trendMaximum = Math.max(...recentTrendPoints.map((point) => point.expenses), 1);
  const expenseTrendDirection = insights?.monthly_trend.expense_direction;
  const insightIcon = (severity: InsightSeverity) => {
    if (severity === "danger" || severity === "warning") return <AlertTriangle aria-hidden="true" size={20} />;
    if (severity === "positive") return <CheckCircle2 aria-hidden="true" size={20} />;
    return <Info aria-hidden="true" size={20} />;
  };

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
          {!loading && insights?.comparison.expense_change_percent !== null && insights?.comparison.expense_change_percent !== undefined ? (
            <small>{Math.abs(insights.comparison.expense_change_percent).toFixed(0)}% {insights.comparison.expense_change_percent >= 0 ? "acima" : "abaixo"} do período anterior</small>
          ) : null}
        </Card>
        <Card className="summary-card">
          <span className="summary-icon savings"><CircleDollarSign size={18} /></span>
          <span>Economizado</span>
          {loading ? <span className="skeleton skeleton-line" /> : <strong>{profit === null ? "—" : formatCurrency(Math.max(profit.lucro, 0))}</strong>}
        </Card>
      </section>

      <section aria-label="Projeção e cartões" className="insight-overview-grid">
        <Card className="insight-overview-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Projeção mensal</span>
              <h2>Como o mês deve terminar</h2>
            </div>
            <span className="insight-overview-icon"><CalendarRange aria-hidden="true" size={20} /></span>
          </div>
          {loading ? (
            <div aria-label="Calculando projeção" className="insight-overview-loading">
              <span className="skeleton skeleton-line" />
              <span className="skeleton skeleton-row" />
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">A projeção está temporariamente indisponível.</p>
          ) : (
            <>
              <strong className={insights.monthly_projection.projected.savings < 0 ? "insight-main-value danger" : "insight-main-value"}>
                {formatCurrency(insights.monthly_projection.projected.savings)}
              </strong>
              <span className="insight-main-label">resultado projetado</span>
              <dl className="insight-breakdown">
                <div><dt>Resultado realizado</dt><dd>{formatCurrency(insights.monthly_projection.realized.savings)}</dd></div>
                <div><dt>Receitas futuras conhecidas</dt><dd className="amount-income">+ {formatCurrency(insights.monthly_projection.known_future.income)}</dd></div>
                <div><dt>Despesas futuras conhecidas</dt><dd className="amount-expense">− {formatCurrency(insights.monthly_projection.known_future.expenses)}</dd></div>
              </dl>
              <p className="insight-overview-note">Baseado apenas no que já está registrado.</p>
            </>
          )}
        </Card>

        <Card className="insight-overview-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Cartões</span>
              <h2>Limite comprometido</h2>
            </div>
            <span className="insight-overview-icon"><CreditCard aria-hidden="true" size={20} /></span>
          </div>
          {loading ? (
            <div aria-label="Calculando comprometimento dos cartões" className="insight-overview-loading">
              <span className="skeleton skeleton-line" />
              <span className="skeleton skeleton-row" />
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">O comprometimento dos cartões está temporariamente indisponível.</p>
          ) : insights.card_commitment.active_cards === 0 ? (
            <div className="insight-empty">
              <strong>Nenhum cartão ativo</strong>
              <p>Adicione um cartão para acompanhar limite e faturas.</p>
              <Link className="text-link" to="/cards">Ir para cartões <ArrowRight size={16} /></Link>
            </div>
          ) : (
            <>
              <strong className="insight-main-value">{formatCurrency(insights.card_commitment.total_committed)}</strong>
              <span className="insight-main-label">de {formatCurrency(insights.card_commitment.total_limit)}</span>
              <div
                aria-label={`${(insights.card_commitment.committed_percent ?? 0).toFixed(0)}% do limite comprometido`}
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={Math.min(100, Math.max(0, insights.card_commitment.committed_percent ?? 0))}
                className="card-commitment-progress"
                role="progressbar"
              >
                <i style={{ width: `${Math.min(100, Math.max(0, insights.card_commitment.committed_percent ?? 0))}%` }} />
              </div>
              <div className="card-commitment-meta">
                <span>{insights.card_commitment.committed_percent?.toFixed(0) ?? "—"}% comprometido</span>
                <span>{formatCurrency(insights.card_commitment.total_available)} disponível</span>
              </div>
              <Link className="text-link insight-overview-link" to="/cards">Ver {insights.card_commitment.active_cards === 1 ? "cartão" : `${insights.card_commitment.active_cards} cartões`} <ArrowRight size={16} /></Link>
            </>
          )}
        </Card>
      </section>

      <section aria-label="Tendências e maiores gastos" className="insight-detail-grid">
        <Card className="insight-detail-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Tendência recente</span>
              <h2>Evolução dos gastos</h2>
            </div>
            <span className="insight-overview-icon">
              {expenseTrendDirection === "down" ? <TrendingDown aria-hidden="true" size={20} /> : <TrendingUp aria-hidden="true" size={20} />}
            </span>
          </div>
          {loading ? (
            <div aria-label="Calculando tendência" className="insight-overview-loading">
              <span className="skeleton skeleton-line" />
              <span className="skeleton skeleton-row" />
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">A tendência está temporariamente indisponível.</p>
          ) : recentTrendPoints.every((point) => point.expenses === 0) ? (
            <div className="insight-empty">
              <strong>Ainda não há histórico suficiente</strong>
              <p>Os próximos meses formarão uma comparação automática dos seus gastos.</p>
            </div>
          ) : (
            <>
              <div className="trend-summary">
                <strong>{insights.monthly_trend.expense_change_percent === null ? "Histórico inicial" : `${Math.abs(insights.monthly_trend.expense_change_percent).toFixed(0)}%`}</strong>
                <span>{expenseTrendDirection === "up" ? "de aumento" : expenseTrendDirection === "down" ? "de redução" : expenseTrendDirection === "stable" ? "sem variação relevante" : "sem base anterior"}</span>
              </div>
              <div className="trend-bars">
                {recentTrendPoints.map((point) => (
                  <div className="trend-bar-item" key={point.month}>
                    <span className="trend-bar-value">{formatCurrency(point.expenses)}</span>
                    <span className="trend-bar-track"><i style={{ height: `${Math.max(6, (point.expenses / trendMaximum) * 100)}%` }} /></span>
                    <small>{new Intl.DateTimeFormat("pt-BR", { month: "short" }).format(new Date(`${point.month}-02T12:00:00`)).replace(".", "")}</small>
                  </div>
                ))}
              </div>
              <p className="insight-overview-note">Comparação de {insights.monthly_trend.comparison_basis === "same_day" ? "períodos equivalentes até o mesmo dia" : "meses completos"}.</p>
            </>
          )}
        </Card>

        <Card className="insight-detail-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Maiores despesas</span>
              <h2>Onde saiu mais dinheiro</h2>
            </div>
            <span className="insight-overview-icon"><ListOrdered aria-hidden="true" size={20} /></span>
          </div>
          {loading ? (
            <div aria-label="Identificando maiores despesas" className="insight-overview-loading">
              {[1, 2, 3].map((item) => <span className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">As maiores despesas estão temporariamente indisponíveis.</p>
          ) : insights.largest_expenses.length === 0 ? (
            <div className="insight-empty">
              <strong>Nenhuma despesa neste período</strong>
              <p>Quando houver gastos, os maiores aparecerão aqui automaticamente.</p>
            </div>
          ) : (
            <div className="largest-expense-list">
              {insights.largest_expenses.slice(0, 3).map((expense, index) => (
                <div className="largest-expense-row" key={`${expense.source}-${expense.id}`}>
                  <span className="largest-expense-rank">{index + 1}</span>
                  <span>
                    <strong>{expense.description}</strong>
                    <small>{expense.category} · {expense.percentage.toFixed(0)}% dos gastos</small>
                  </span>
                  <strong>{formatCurrency(expense.amount)}</strong>
                </div>
              ))}
              <Link className="text-link insight-overview-link" to="/transactions">Ver movimentações <ArrowRight size={16} /></Link>
            </div>
          )}
        </Card>
      </section>

      <section aria-label="Recorrências e gastos fora do padrão" className="insight-detail-grid" id="recurrences">
        <Card className="insight-detail-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Recorrências</span>
              <h2>Despesas que costumam se repetir</h2>
            </div>
            <span className="insight-overview-icon"><Repeat2 aria-hidden="true" size={20} /></span>
          </div>
          {loading ? (
            <div aria-label="Identificando recorrências" className="insight-overview-loading">
              {[1, 2, 3].map((item) => <span className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">As recorrências estão temporariamente indisponíveis.</p>
          ) : insights.recurring_expenses.length === 0 ? (
            <div className="insight-empty">
              <strong>Ainda não há padrões confiáveis</strong>
              <p>São necessárias pelo menos três ocorrências regulares para identificar uma recorrência.</p>
            </div>
          ) : (
            <div className="financial-pattern-list">
              {insights.recurring_expenses.slice(0, 3).map((recurrence) => (
                <div className="financial-pattern-row" key={recurrence.pattern_id}>
                  <span>
                    <strong>{recurrence.description}</strong>
                    <small>{frequencyLabels[recurrence.frequency]} · {recurrence.occurrence_count} ocorrências{recurrence.next_occurrence ? ` · próxima em ${formatDate(recurrence.next_occurrence)}` : ""}</small>
                  </span>
                  <span className="financial-pattern-amount">
                    <strong>{formatCurrency(recurrence.typical_amount)}</strong>
                    <small>{recurrence.confidence === "high" ? "Alta confiança" : "Provável"}</small>
                  </span>
                </div>
              ))}
              <p className="insight-overview-note">Padrões calculados pelo histórico; datas futuras são estimativas.</p>
            </div>
          )}
        </Card>

        <Card className="insight-detail-card">
          <div className="card-heading card-heading-row">
            <div>
              <span className="section-kicker">Fora do padrão</span>
              <h2>Gastos que se destacaram</h2>
            </div>
            <span className="insight-overview-icon"><ScanSearch aria-hidden="true" size={20} /></span>
          </div>
          {loading ? (
            <div aria-label="Analisando gastos fora do padrão" className="insight-overview-loading">
              {[1, 2].map((item) => <span className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">A análise de gastos está temporariamente indisponível.</p>
          ) : insights.unusual_expenses.length === 0 ? (
            <div className="insight-empty">
              <strong>Nenhum gasto relevante fora do padrão</strong>
              <p>A comparação usa somente o histórico anterior de cada movimentação.</p>
            </div>
          ) : (
            <div className="financial-pattern-list">
              {insights.unusual_expenses.slice(0, 3).map((expense) => (
                <div className="financial-pattern-row" key={`${expense.source}-${expense.id}`}>
                  <span>
                    <strong>{expense.description}</strong>
                    <small>{expense.reason}</small>
                  </span>
                  <span className="financial-pattern-amount">
                    <strong>{formatCurrency(expense.amount)}</strong>
                    <small>{expense.category}</small>
                  </span>
                </div>
              ))}
              <Link className="text-link insight-overview-link" to="/transactions">Ver movimentações <ArrowRight size={16} /></Link>
            </div>
          )}
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
          {loading ? (
            <div className="attention-list" aria-label="Analisando suas finanças">
              {[1, 2].map((item) => <span className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : insights === null ? (
            <p className="section-unavailable">Os insights estão temporariamente indisponíveis. Seu resumo financeiro continua acima.</p>
          ) : (
            <div className="attention-list">
              {insights.attention.map((item) => (
                <div className={`attention-item attention-${item.severity}`} key={item.code}>
                  <span>{insightIcon(item.severity)}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.description}</p>
                    {item.action_path && item.action_label ? <Link className="attention-action" to={item.action_path}>{item.action_label}<ArrowRight size={14} /></Link> : null}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="attention-note">Análises automáticas por regras claras. A Lumi ainda está em preparação.</p>
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
