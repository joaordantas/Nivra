import { Landmark, Link2 } from "lucide-react";
import { useState } from "react";
import { PluggyConnect } from "react-pluggy-connect";

import { useTheme } from "../../app/providers";
import { api } from "../../services/api";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Feedback } from "../ui/Feedback";


export function OpenFinanceConnectCard() {
  const { theme } = useTheme();
  const [connectToken, setConnectToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

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
          onSuccess={({ item }) => {
            setMessage(`Conexão Sandbox criada (${item.id}). A sincronização dos dados será implementada na próxima etapa.`);
            setConnectToken(null);
          }}
          theme={theme}
        />
      ) : null}
    </Card>
  );
}

