import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  CreditCard,
  Landmark,
  Link2,
  LoaderCircle,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PluggyConnect } from "react-pluggy-connect";

import { useTheme } from "../../app/providers";
import { api } from "../../services/api";
import type { Account, OpenFinanceConnection, OpenFinanceExternalAccount } from "../../types";
import { formatCurrency } from "../../utils/formatters";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Feedback } from "../ui/Feedback";
import { Modal } from "../ui/Modal";

type LinkChoice = "existing" | "create";

const externalAccountTypeLabels: Record<string, string> = {
  BANK: "Conta bancária",
  CREDIT: "Cartão de crédito",
  CREDIT_CARD: "Cartão de crédito",
  INVESTMENT: "Investimento",
};

function formatLastSync(value: string | null) {
  if (!value) return "Ainda não sincronizado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Atualização disponível";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds >= 0 && seconds < 60) return "Agora mesmo";
  if (seconds >= 60 && seconds < 60 * 60) return `Há ${Math.floor(seconds / 60)} min`;
  if (date.toDateString() === new Date().toDateString()) {
    return `Hoje, ${new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date)}`;
  }
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function connectionStatus(connection: OpenFinanceConnection, syncing: boolean) {
  if (connection.desconectada_em) return { label: "Desconectado", tone: "disconnected", icon: Unplug };
  if (syncing) return { label: "Atualizando dados", tone: "updating", icon: LoaderCircle };
  if (connection.status === "error") return { label: "Atenção necessária", tone: "attention", icon: CircleAlert };
  if (connection.ultimo_evento_status === "erro") return { label: "Erro de atualização", tone: "error", icon: AlertCircle };
  return { label: "Conectado", tone: "connected", icon: CheckCircle2 };
}

interface OpenFinanceConnectCardProps {
  accounts: Account[];
  onAccountsChanged: () => Promise<void>;
}

export function OpenFinanceConnectCard({ accounts, onAccountsChanged }: OpenFinanceConnectCardProps) {
  const { theme } = useTheme();
  const [connectToken, setConnectToken] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [connections, setConnections] = useState<OpenFinanceConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [externalAccounts, setExternalAccounts] = useState<Record<number, OpenFinanceExternalAccount[]>>({});
  const [linkingExternalAccountId, setLinkingExternalAccountId] = useState<number | null>(null);
  const [accountToLink, setAccountToLink] = useState<OpenFinanceExternalAccount | null>(null);
  const [linkChoice, setLinkChoice] = useState<LinkChoice>("existing");
  const [selectedNivraAccountId, setSelectedNivraAccountId] = useState(0);

  const loadConnections = useCallback(async () => {
    try {
      setLoadingConnections(true);
      const loadedConnections = await api.getOpenFinanceConnections();
      setConnections(loadedConnections);
      const accountEntries = await Promise.all(loadedConnections.map(async (connection) => [
        connection.id,
        await api.getOpenFinanceExternalAccounts(connection.id),
      ] as const));
      setExternalAccounts(Object.fromEntries(accountEntries));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as conexões bancárias.");
    } finally {
      setLoadingConnections(false);
    }
  }, []);

  useEffect(() => { void loadConnections(); }, [loadConnections]);

  const accountsAvailableForLink = useMemo(() => accounts.filter((account) => (
    account.ativo && (account.conta_externa_id === null || account.conta_externa_id === accountToLink?.id)
  )), [accountToLink?.id, accounts]);

  async function openConnect() {
    try {
      setConnecting(true);
      setError("");
      setMessage("");
      const response = await api.createOpenFinanceConnectToken();
      setConnectToken(response.connect_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível iniciar a conexão bancária.");
    } finally {
      setConnecting(false);
    }
  }

  async function completeConnection(itemId: string) {
    setConnectToken(null);
    setConnecting(true);
    setError("");
    setMessage("");
    try {
      const connection = await api.completeOpenFinanceConnection(itemId);
      setMessage(`${connection.instituicao_nome} foi conectado. Atualize os dados para trazer contas e movimentações disponíveis.`);
      await loadConnections();
    } catch {
      setError("O banco foi selecionado, mas não foi possível concluir a conexão com a Nivra.");
    } finally {
      setConnecting(false);
    }
  }

  async function syncConnection(connection: OpenFinanceConnection) {
    try {
      setSyncingId(connection.id);
      setError("");
      setMessage("");
      const result = await api.syncOpenFinanceConnection(connection.id);
      const processed = result.transacoes_criadas + result.transacoes_atualizadas;
      setMessage(`${connection.instituicao_nome}: dados atualizados${processed ? `, com ${processed} movimentações processadas` : ""}.`);
      await Promise.all([loadConnections(), onAccountsChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar esta conexão. Tente novamente.");
      await loadConnections();
    } finally {
      setSyncingId(null);
    }
  }

  function openLinkDialog(externalAccount: OpenFinanceExternalAccount) {
    setAccountToLink(externalAccount);
    setSelectedNivraAccountId(0);
    setLinkChoice(accounts.some((account) => account.ativo && account.conta_externa_id === null) ? "existing" : "create");
    setError("");
  }

  async function submitLink() {
    if (!accountToLink) return;
    try {
      setLinkingExternalAccountId(accountToLink.id);
      setError("");
      setMessage("");
      const link = linkChoice === "create"
        ? await api.createAccountFromOpenFinance(accountToLink.id)
        : await api.linkOpenFinanceExternalAccount(accountToLink.id, selectedNivraAccountId);
      setAccountToLink(null);
      setMessage(linkChoice === "create"
        ? `${link.conta_nivra_nome} foi criada com saldo informado pelo banco.`
        : `${accountToLink.nome} foi vinculada a ${link.conta_nivra_nome}.`);
      await Promise.all([loadConnections(), onAccountsChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar o vínculo desta conta.");
    } finally {
      setLinkingExternalAccountId(null);
    }
  }

  function renderExternalAccount(account: OpenFinanceExternalAccount) {
    const isLinked = Boolean(account.conta_nivra_id);
    const canLink = account.pode_vincular_conta_nivra;
    const accountType = externalAccountTypeLabels[account.tipo.toUpperCase()] ?? "Conta bancária";
    return (
      <article className="open-finance-external-account" key={account.id}>
        <div className="open-finance-external-account-summary">
          <span className={`open-finance-external-account-icon ${canLink ? "" : "credit"}`}>{canLink ? <Landmark aria-hidden="true" size={17} /> : <CreditCard aria-hidden="true" size={17} />}</span>
          <span><strong>{account.nome}</strong><small>{accountType} · {account.quantidade_transacoes} movimentações</small></span>
        </div>
        <div className="open-finance-external-account-side">
          <strong>{account.saldo === null ? "Saldo indisponível" : formatCurrency(account.saldo)}</strong>
          {isLinked ? <span className="open-finance-link-state"><CheckCircle2 aria-hidden="true" size={13} />Vinculada a {account.conta_nivra_nome}</span> : null}
        </div>
        {canLink && !isLinked ? <Button disabled={linkingExternalAccountId !== null} onClick={() => openLinkDialog(account)} type="button" variant="secondary"><Link2 aria-hidden="true" size={15} />Vincular à Nivra</Button> : null}
        {!canLink ? <small className="open-finance-read-only">Cartão externo disponível somente para consulta nesta versão.</small> : null}
      </article>
    );
  }

  return (
    <Card as="section" className="open-finance-connect-card" aria-label="Conexões bancárias">
      <div className="open-finance-heading">
        <span className="open-finance-icon"><Landmark aria-hidden="true" size={22} /></span>
        <div className="open-finance-copy"><span className="section-kicker">Open Finance <span className="open-finance-demo-badge">Demonstração</span></span><h2>Suas conexões bancárias</h2><p>Conecte um banco de teste para trazer saldos e movimentações disponíveis para a Nivra.</p></div>
        <Button disabled={connecting || syncingId !== null} onClick={() => void openConnect()} type="button">{connecting ? <LoaderCircle aria-hidden="true" className="spin" size={17} /> : <Link2 aria-hidden="true" size={17} />}{connecting ? "Preparando..." : "Conectar banco"}</Button>
      </div>
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}
      {loadingConnections ? <div className="open-finance-loading-list" aria-live="polite"><span className="skeleton open-finance-skeleton" /><span className="skeleton open-finance-skeleton" /></div> : null}
      {!loadingConnections && connections.length === 0 ? <EmptyState action={<Button disabled={connecting} onClick={() => void openConnect()} type="button"><Link2 aria-hidden="true" size={16} />Conectar banco</Button>} description="Conecte um banco para importar suas movimentações de demonstração." icon={Building2} title="Conecte suas contas" /> : null}
      {!loadingConnections && connections.length > 0 ? <div className="open-finance-connections" aria-live="polite">
        {connections.map((connection) => {
          const external = externalAccounts[connection.id] ?? [];
          const totalTransactions = external.reduce((total, account) => total + account.quantidade_transacoes, 0);
          const status = connectionStatus(connection, syncingId === connection.id);
          const StatusIcon = status.icon;
          const hasError = status.tone === "attention" || status.tone === "error";
          return <article className="open-finance-connection" key={connection.id}>
            <div className="open-finance-connection-header"><span className={`open-finance-connection-icon ${status.tone}`}><StatusIcon aria-hidden="true" className={status.tone === "updating" ? "spin" : ""} size={19} /></span><div><h3>{connection.instituicao_nome}</h3><span className={`connection-status ${status.tone}`}>{status.label}</span></div>{!connection.desconectada_em ? <Button disabled={syncingId !== null || connecting} onClick={() => void syncConnection(connection)} type="button" variant="secondary"><RefreshCw aria-hidden="true" className={syncingId === connection.id ? "spin" : ""} size={15} />{syncingId === connection.id ? "Atualizando..." : "Atualizar dados"}</Button> : null}</div>
            <div className="open-finance-connection-meta"><span>Última atualização <strong>{formatLastSync(connection.ultima_sincronizacao_em)}</strong></span><span>{external.length} {external.length === 1 ? "conta" : "contas"} · {totalTransactions} {totalTransactions === 1 ? "movimentação" : "movimentações"}</span></div>
            {hasError ? <p className="open-finance-error-copy">Não foi possível atualizar esta conexão. Você pode tentar novamente mais tarde.</p> : null}
            {connection.desconectada_em ? <p className="open-finance-error-copy">Esta conexão não recebe novas atualizações. O histórico importado foi preservado.</p> : null}
            {!connection.desconectada_em && external.length === 0 ? <p className="open-finance-empty-accounts">Conexão pronta. Atualize os dados para importar contas e movimentações.</p> : null}
            {external.length > 0 ? <div className="open-finance-external-accounts">{external.map(renderExternalAccount)}</div> : null}
          </article>;
        })}
      </div> : null}
      {accountToLink ? <Modal onClose={() => setAccountToLink(null)} title="Como deseja usar esta conta?"><div className="open-finance-link-dialog"><p><strong>{accountToLink.nome}</strong> terá o saldo atual informado pelo banco conectado.</p>{accountsAvailableForLink.length > 0 ? <label className="open-finance-link-option"><input checked={linkChoice === "existing"} name="link-choice" onChange={() => setLinkChoice("existing")} type="radio" /><span><strong>Vincular a uma conta existente</strong><small>Use uma conta Nivra que já representa este mesmo dinheiro.</small></span></label> : null}<label className="open-finance-link-option"><input checked={linkChoice === "create"} name="link-choice" onChange={() => setLinkChoice("create")} type="radio" /><span><strong>Criar uma conta na Nivra</strong><small>Uma nova conta será criada e vinculada ao banco.</small></span></label>{linkChoice === "existing" ? <label>Conta Nivra<select aria-label="Conta Nivra existente" onChange={(event) => setSelectedNivraAccountId(Number(event.target.value))} value={selectedNivraAccountId || ""}><option disabled value="">Selecione uma conta</option>{accountsAvailableForLink.map((account) => <option key={account.id} value={account.id}>{account.nome}</option>)}</select></label> : null}<Button disabled={linkingExternalAccountId !== null || (linkChoice === "existing" && !selectedNivraAccountId)} onClick={() => void submitLink()} type="button">{linkingExternalAccountId === accountToLink.id ? <LoaderCircle aria-hidden="true" className="spin" size={17} /> : <ChevronRight aria-hidden="true" size={17} />}{linkChoice === "create" ? "Criar e vincular conta" : "Salvar vínculo"}</Button></div></Modal> : null}
      {connectToken ? <PluggyConnect allowFullscreen connectToken={connectToken} countries={["BR"]} includeSandbox language="pt" onClose={() => setConnectToken(null)} onError={() => { setError("A conexão de demonstração não foi concluída."); setConnectToken(null); }} onLoadError={() => { setError("Não foi possível carregar o ambiente seguro de conexão."); setConnectToken(null); }} onSuccess={({ item }) => void completeConnection(item.id)} theme={theme} /> : null}
    </Card>
  );
}
