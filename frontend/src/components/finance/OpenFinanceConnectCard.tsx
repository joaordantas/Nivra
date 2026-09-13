import { CheckCircle2, Landmark, Link2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PluggyConnect } from "react-pluggy-connect";

import { useTheme } from "../../app/providers";
import { api } from "../../services/api";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Feedback } from "../ui/Feedback";
import type { OpenFinanceConnection } from "../../types";


export function OpenFinanceConnectCard() {
  const { theme } = useTheme();
  const [connectToken, setConnectToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [connections, setConnections] = useState<OpenFinanceConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);

  const loadConnections = useCallback(async () => {
    try {
      setLoadingConnections(true);
      setConnections(await api.getOpenFinanceConnections());
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
              <small>Sincronização: {connection.ultima_sincronizacao_em ? "Realizada" : "Ainda não realizada"}</small>
            </span>
            <span className="status-badge active">Conectado</span>
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
