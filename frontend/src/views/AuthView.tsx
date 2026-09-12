import { ArrowRight, CheckCircle2, Moon, PiggyBank, ShieldCheck, Sparkles, Sun } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "../services/api";
import { Button } from "../components/ui/Button";
import { Feedback } from "../components/ui/Feedback";
import type { User } from "../types";
import { useTheme } from "../app/providers";

interface AuthViewProps {
  onLogin: (user: User) => void;
}

export function AuthView({ onLogin }: AuthViewProps) {
  const { theme, toggleTheme } = useTheme();
  const [tab, setTab] = useState<"login" | "cadastro">("login");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [name, setName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    try {
      onLogin(await api.login(loginEmail, loginPassword));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const user = await api.register({
        usuario: name,
        email: registerEmail,
        senha: registerPassword,
        tipo_perfil: "Apenas Financeiro",
      });
      setMessage("Conta criada. Seu espaço financeiro está pronto.");
      onLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar sua conta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <div className="product-brand auth-brand">
          <span className="product-mark"><PiggyBank aria-hidden="true" size={23} /></span>
          <span><strong>Nivra</strong><small>Seu dinheiro, mais claro</small></span>
        </div>
        <div className="auth-copy">
          <span className="auth-kicker"><Sparkles size={16} /> Clareza sem complicação</span>
          <h1>Cuide melhor do seu dinheiro gastando menos tempo.</h1>
          <p>Registre suas movimentações e encontre rapidamente o que merece sua atenção.</p>
          <div className="auth-benefits">
            <span><CheckCircle2 size={18} /> Resumo financeiro em poucos segundos</span>
            <span><CheckCircle2 size={18} /> Informações importantes no lugar certo</span>
            <span><ShieldCheck size={18} /> Uma visão organizada para o seu dia a dia</span>
          </div>
        </div>
        <small className="auth-version">Nivra · Alpha</small>
      </section>

      <section className="auth-form-panel">
        <button aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"} className="icon-button auth-theme-button" onClick={toggleTheme} type="button">
          {theme === "dark" ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
        </button>
        <div className="auth-form-wrap">
          <div className="auth-form-heading">
            <h2>{tab === "login" ? "Boas-vindas" : "Crie sua conta"}</h2>
            <p>{tab === "login" ? "Entre para acompanhar suas finanças." : "Comece a organizar sua vida financeira."}</p>
          </div>

          <div className="auth-tabs" role="tablist">
            <button aria-selected={tab === "login"} className={tab === "login" ? "is-active" : ""} onClick={() => setTab("login")} role="tab" type="button">Entrar</button>
            <button aria-selected={tab === "cadastro"} className={tab === "cadastro" ? "is-active" : ""} onClick={() => setTab("cadastro")} role="tab" type="button">Criar conta</button>
          </div>

          {error ? <Feedback>{error}</Feedback> : null}
          {message ? <Feedback tone="success">{message}</Feedback> : null}

          {tab === "login" ? (
            <form className="form-grid auth-form" onSubmit={handleLogin}>
              <label>E-mail<input autoComplete="email" onChange={(event) => setLoginEmail(event.target.value)} placeholder="voce@exemplo.com" type="email" value={loginEmail} /></label>
              <label>Senha<input autoComplete="current-password" onChange={(event) => setLoginPassword(event.target.value)} placeholder="Sua senha" type="password" value={loginPassword} /></label>
              <Link className="auth-text-link" to="/forgot-password">Esqueci minha senha</Link>
              <Button disabled={loading} type="submit">{loading ? "Entrando..." : <>Entrar <ArrowRight size={18} /></>}</Button>
            </form>
          ) : (
            <form className="form-grid auth-form" onSubmit={handleRegister}>
              <label>Seu nome<input autoComplete="name" onChange={(event) => setName(event.target.value)} placeholder="Como podemos chamar você?" value={name} /></label>
              <label>E-mail<input autoComplete="email" onChange={(event) => setRegisterEmail(event.target.value)} placeholder="voce@exemplo.com" type="email" value={registerEmail} /></label>
              <label>Senha<input autoComplete="new-password" minLength={12} onChange={(event) => setRegisterPassword(event.target.value)} placeholder="No mínimo 12 caracteres" type="password" value={registerPassword} /></label>
              <Button disabled={loading} type="submit">{loading ? "Criando..." : <>Criar minha conta <ArrowRight size={18} /></>}</Button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
