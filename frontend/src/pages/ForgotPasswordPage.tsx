import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Mail } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Feedback } from "../components/ui/Feedback";
import { api } from "../services/api";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(""); setMessage("");
    try { setMessage((await api.forgotPassword(email)).message); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível continuar."); }
    finally { setLoading(false); }
  }

  return <main className="standalone-auth-page"><section className="standalone-auth-card">
    <span className="standalone-auth-icon"><Mail size={22} /></span>
    <h1>Recuperar senha</h1>
    <p>Informe o e-mail da sua conta. Se ele estiver cadastrado, enviaremos um link válido por 30 minutos.</p>
    {error ? <Feedback>{error}</Feedback> : null}
    {message ? <Feedback tone="success">{message}</Feedback> : null}
    <form className="form-grid" onSubmit={submit}>
      <label>E-mail<input autoComplete="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} /></label>
      <Button disabled={loading} type="submit">{loading ? "Enviando..." : "Enviar instruções"}</Button>
    </form>
    <Link className="auth-back-link" to="/login"><ArrowLeft size={16} /> Voltar para entrar</Link>
  </section></main>;
}
