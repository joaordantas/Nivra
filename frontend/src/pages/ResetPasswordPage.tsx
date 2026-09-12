import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Feedback } from "../components/ui/Feedback";
import { api } from "../services/api";

export function ResetPasswordPage() {
  const token = useMemo(() => {
    const value = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";
    window.history.replaceState(null, "", window.location.pathname);
    return value;
  }, []);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "Este link de recuperação está incompleto.");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    try { setMessage((await api.resetPassword(token, password, confirmation)).message); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível redefinir a senha."); }
    finally { setLoading(false); }
  }

  return <main className="standalone-auth-page"><section className="standalone-auth-card">
    <span className="standalone-auth-icon"><KeyRound size={22} /></span>
    <h1>Crie uma nova senha</h1><p>Use uma senha com pelo menos 12 caracteres. Ao concluir, todas as sessões abertas serão encerradas.</p>
    {error ? <Feedback>{error}</Feedback> : null}{message ? <Feedback tone="success">{message}</Feedback> : null}
    {!message && token ? <form className="form-grid" onSubmit={submit}>
      <label>Nova senha<input autoComplete="new-password" minLength={12} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label>
      <label>Confirmar senha<input autoComplete="new-password" minLength={12} onChange={(event) => setConfirmation(event.target.value)} required type="password" value={confirmation} /></label>
      <Button disabled={loading} type="submit">{loading ? "Alterando..." : "Redefinir senha"}</Button>
    </form> : null}
    <Link className="auth-back-link" to="/login">Voltar para entrar</Link>
  </section></main>;
}
