import { CheckCircle2, CreditCard, Landmark, Link2, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PluggyConnect } from "react-pluggy-connect";

import { useTheme } from "../../app/providers";
import { api } from "../../services/api";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Feedback } from "../ui/Feedback";
import type { Account, OpenFinanceConnection, OpenFinanceExternalAccount } from "../../types";


const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function formatSyncDate(value: string | null) {
  if (!value) return "Ainda não realizada";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


interface OpenFinanceConnectCardProps {
  accounts: Account[];
  onAccountsChanged: () => Promise<void>;
}


export function OpenFinanceConnectCard({ accounts, onAccountsChanged }: OpenFinanceConnectCardProps) {
  const { theme } = useTheme();
  const [connectToken, setConnectToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [connections, setConnections] = useState<OpenFinanceConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [externalAccounts, setExternalAccounts] = useState<Record<number, OpenFinanceExternalAccount[]>>({});
  const [selectedAccountIds, setSelectedAccountIds] = useState<Record<number, number>>({});
  const [linkingExternalAccountId, setLinkingExternalAccountId] = useState<number | null>(null);

  const loadConnections = useCallback(async () => {
    try {
      setLoadingConnections(true);
      const loadedConnections = await api.getOpenFinanceConnections();
      setConnections(loadedConnections);
      const accountEntries = await Promise.all(
        loadedConnections.map(async (connection) => [
          connection.id,
          await api.getOpenFinanceExternalAccounts(connection.id),
        ] as const),
      );
      setExternalAccounts(Object.fromEntries(accountEntries));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as conexões bancárias.");
    } finally {
      setLoadingConnections(false);
    }
  }, []);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  async function openConnect() {
    try {
      setLoading(true);
      setError("");
      setMessage("");
      const response = await api.createOpenFinanceConnectToken();
      setConnectToken(response.connect_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível iniciar a conexão bancária.");
    } finally {
      setLoading(false);
    }
  }

  async function completeConnection(itemId: string) {
    setConnectToken(null);
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const connection = await api.completeOpenFinanceConnection(itemId);
      setMessage(`${connection.instituicao_nome} foi vinculada à Nivra. A sincronização ainda não foi realizada.`);
      await loadConnections();
    } catch {
      setError("Banco conectado, mas não foi possível concluir o vínculo com a Nivra.");
    } finally {
      setLoading(false);
    }
  }

  async function syncConnection(connection: OpenFinanceConnection) {
    try {
      setSyncingId(connection.id);
      setError("");
      setMessage("");
      const result = await api.syncOpenFinanceConnection(connection.id);
      setMessage(
        `${connection.instituicao_nome}: ${result.transacoes_processadas} transações sincronizadas.`,
      );
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível sincronizar esta conexão.");
      await loadConnections();
    } finally {
      setSyncingId(null);
    }
  }

  function availableAccounts(externalAccount: OpenFinanceExternalAccount) {
    return accounts.filter((account) => (
      account.ativo
      && (account.conta_externa_id === null || account.conta_externa_id === externalAccount.id)
    ));
  }

  async function linkExternalAccount(externalAccount: OpenFinanceExternalAccount) {
    const accountId = selectedAccountIds[externalAccount.id] ?? externalAccount.conta_nivra_id;
    if (!accountId) {
      setError("Selecione uma conta Nivra para criar o vínculo.");
      return;
    }
    try {
      setLinkingExternalAccountId(externalAccount.id);
      setError("");
      setMessage("");
      const link = await api.linkOpenFinanceExternalAccount(externalAccount.id, accountId);
      setMessage(`${externalAccount.nome} foi vinculada a ${link.conta_nivra_nome}.`);
      await Promise.all([loadConnections(), onAccountsChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível vincular esta conta.");
    } finally {
      setLinkingExternalAccountId(null);
    }
  }

  async function createNivraAccount(externalAccount: OpenFinanceExternalAccount) {
    try {
      setLinkingExternalAccountId(externalAccount.id);
      setError("");
      setMessage("");
      const link = await api.createAccountFromOpenFinance(externalAccount.id);
      setMessage(`${link.conta_nivra_nome} foi criada com o saldo sincronizado pelo banco.`);
      await Promise.all([loadConnections(), onAccountsChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar a conta Nivra.");
    } finally {
      setLinkingExternalAccountId(null);
    }
  }

  return (
    <Card as="section" className="open-finance-connect-card">
      <span className="open-finance-icon"><Landmark aria-hidden="true" size={22} /></span>
      <div className="open-finance-copy">
        <span className="section-kicker">Open Finance · Sandbox</span>
        <h2>Conecte um banco fictício</h2>
        <p>Experimente o fluxo da Pluggy com dados de teste. Nenhuma credencial bancária real deve ser usada nesta versão.</p>
      </div>
      <Button disabled={loading} onClick={() => void openConnect()} type="button">
        <Link2 aria-hidden="true" size={17} />
        {loading ? "Preparando..." : "Conectar banco"}
      </Button>

      {error ? <div className="open-finance-feedback"><Feedback>{error}</Feedback></div> : null}
      {message ? <div className="open-finance-feedback"><Feedback tone="success">{message}</Feedback></div> : null}

      <div className="open-finance-connections" aria-live="polite">
        {loadingConnections ? <span className="open-finance-loading">Carregando conexões...</span> : null}
        {!loadingConnections && connections.length === 0 ? (
          <span className="open-finance-empty">Nenhum banco Sandbox vinculado à Nivra.</span>
        ) : null}
        {connections.map((connection) => (
          <div className="open-finance-connection" key={connection.id}>
            <span className="open-finance-connection-icon"><CheckCircle2 aria-hidden="true" size={18} /></span>
            <span>
              <strong>{connection.instituicao_nome}</strong>
              <small>Sincronização: {formatSyncDate(connection.ultima_sincronizacao_em)}</small>
              {connection.ultimo_evento_status === "erro" && connection.ultimo_erro ? (
                <small className="open-finance-sync-error">{connection.ultimo_erro}</small>
              ) : null}
            </span>
            <Button
              disabled={syncingId !== null}
              onClick={() => void syncConnection(connection)}
              type="button"
              variant="secondary"
            >
              <RefreshCw aria-hidden="true" className={syncingId === connection.id ? "spin" : ""} size={15} />
              {syncingId === connection.id ? "Sincronizando..." : "Sincronizar"}
            </Button>
            {(externalAccounts[connection.id] ?? []).length > 0 ? (
              <div className="open-finance-external-accounts">
                {(externalAccounts[connection.id] ?? []).map((account) => (
                  <div className="open-finance-external-account" key={account.id}>
                    <span className="open-finance-external-account-summary">
                      <strong>{account.nome}</strong>
                      <small>{account.quantidade_transacoes} transações</small>
                    </span>
                    <strong className="open-finance-external-balance">{account.saldo === null ? "Saldo indisponível" : currency.format(account.saldo)}</strong>
                    {account.pode_vincular_conta_nivra ? (
                      <div className="open-finance-link-controls">
                        {account.conta_nivra_nome ? (
                          <small className="open-finance-linked"><CheckCircle2 size={13} />Vinculada a {account.conta_nivra_nome}</small>
                        ) : null}
                        {availableAccounts(account).length > 0 ? (
                          <select
                            aria-label={`Conta Nivra para ${account.nome}`}
                            onChange={(event) => setSelectedAccountIds((current) => ({
                              ...current,
                              [account.id]: Number(event.target.value),
                            }))}
                            value={selectedAccountIds[account.id] ?? account.conta_nivra_id ?? ""}
                          >
                            <option disabled value="">Vincular a uma conta existente</option>
                            {availableAccounts(account).map((nivraAccount) => (
                              <option key={nivraAccount.id} value={nivraAccount.id}>{nivraAccount.nome}</option>
                            ))}
                          </select>
                        ) : null}
                        {availableAccounts(account).length > 0 ? (
                          <Button
                            disabled={linkingExternalAccountId !== null}
                            onClick={() => void linkExternalAccount(account)}
                            type="button"
                            variant="secondary"
                          >
                            <Link2 size={14} />{account.conta_nivra_id ? "Salvar vínculo" : "Vincular"}
                          </Button>
                        ) : null}
                        {!account.conta_nivra_id ? (
                          <Button
                            disabled={linkingExternalAccountId !== null}
                            onClick={() => void createNivraAccount(account)}
                            type="button"
                            variant="ghost"
                          >
                            <Plus size={14} />Criar conta Nivra
                          </Button>
                        ) : null}
                      </div>
                    ) : (
                      <small className="open-finance-link-note"><CreditCard size={13} />Cartão externo — integração com cartões será feita separadamente.</small>
                    )}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {connectToken ? (
        <PluggyConnect
          allowFullscreen
          connectToken={connectToken}
          countries={["BR"]}
          includeSandbox
          language="pt"
          onClose={() => setConnectToken(null)}
          onError={(widgetError) => {
            setError(widgetError.message || "A conexão Sandbox não foi concluída.");
            setConnectToken(null);
          }}
          onLoadError={() => {
            setError("Não foi possível carregar o ambiente seguro da Pluggy.");
            setConnectToken(null);
          }}
          onSuccess={({ item }) => completeConnection(item.id)}
          theme={theme}
        />
      ) : null}
    </Card>
  );
}
