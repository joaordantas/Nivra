import { useEffect, useMemo, useState } from "react";
import { BadgeCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../app/providers";
import { Feedback } from "../components/ui/Feedback";
import { api } from "../services/api";

export function VerifyEmailPage() {
  const { isAuthenticated, refreshUser } = useAuth();
  const token = useMemo(() => {
    const value = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";
    window.history.replaceState(null, "", window.location.pathname);
    return value;
  }, []);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "Este link de verificação está incompleto.");

  useEffect(() => {
    if (!token) return;
    let active = true;
    api.verifyEmail(token).then(async (result) => {
      try { await refreshUser(); } catch { /* O link também funciona sem sessão ativa. */ }
      if (active) setMessage(result.message);
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Não foi possível verificar o e-mail.");
    });
    return () => { active = false; };
  }, [refreshUser, token]);

  return <main className="standalone-auth-page"><section className="standalone-auth-card">
    <span className="standalone-auth-icon"><BadgeCheck size={22} /></span>
    <h1>Verificação de e-mail</h1>
    {!message && !error ? <p>Validando seu link seguro...</p> : null}
    {error ? <Feedback>{error}</Feedback> : null}{message ? <Feedback tone="success">{message}</Feedback> : null}
    <Link className="auth-back-link" to={isAuthenticated ? "/dashboard" : "/login"}>{isAuthenticated ? "Ir para o início" : "Voltar para entrar"}</Link>
  </section></main>;
}
