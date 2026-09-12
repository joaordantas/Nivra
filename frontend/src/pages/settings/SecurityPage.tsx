import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Feedback } from "../../components/ui/Feedback";
import { PageHeader } from "../../components/ui/PageHeader";
import { api } from "../../services/api";

export function SecurityPage() {
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(""); setMessage("");
    try {
      setMessage((await api.changePassword(current, password, confirmation)).message);
      setCurrent(""); setPassword(""); setConfirmation("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível alterar a senha."); }
    finally { setLoading(false); }
  }

  return <div className="page-stack">
    <Link className="back-link" to="/settings"><ArrowLeft size={17} />Configurações</Link>
    <PageHeader description="Atualize sua credencial e encerre automaticamente as outras sessões." eyebrow="Sua conta" title="Segurança" />
    <Card className="security-card">
      <span className="standalone-auth-icon"><KeyRound size={22} /></span>
      <div><h2>Alterar senha</h2><p>Use pelo menos 12 caracteres. Este dispositivo continuará conectado; os demais serão desconectados.</p></div>
      {error ? <Feedback>{error}</Feedback> : null}{message ? <Feedback tone="success">{message}</Feedback> : null}
      <form className="form-grid" onSubmit={submit}>
        <label>Senha atual<input autoComplete="current-password" onChange={(event) => setCurrent(event.target.value)} required type="password" value={current} /></label>
        <label>Nova senha<input autoComplete="new-password" minLength={12} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label>
        <label>Confirmar nova senha<input autoComplete="new-password" minLength={12} onChange={(event) => setConfirmation(event.target.value)} required type="password" value={confirmation} /></label>
        <Button disabled={loading} type="submit">{loading ? "Alterando..." : "Alterar senha"}</Button>
      </form>
    </Card>
  </div>;
}
