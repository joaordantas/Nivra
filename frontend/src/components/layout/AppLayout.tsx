import { Moon, PiggyBank, Sun } from "lucide-react";
import { Outlet } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { MobileNavigation } from "./MobileNavigation";
import { AlphaBadge } from "./AlphaBadge";
import { Sidebar } from "./Sidebar";
import { useTheme } from "../../app/providers";
import { useAuth } from "../../app/providers";
import { ApiError, api } from "../../services/api";

export function AppLayout() {
  const { theme, toggleTheme } = useTheme();
  const { authNotice, user } = useAuth();
  const [registrationNotice, setRegistrationNotice] = useState(authNotice);
  const [verificationMessage, setVerificationMessage] = useState("");
  const [verificationError, setVerificationError] = useState(false);
  const [sendingVerification, setSendingVerification] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const verificationRequestInFlight = useRef(false);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const timer = window.setTimeout(
      () => setCooldownSeconds((current) => Math.max(0, current - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [cooldownSeconds]);

  async function resendVerification() {
    if (verificationRequestInFlight.current || cooldownSeconds > 0) return;
    verificationRequestInFlight.current = true;
    setSendingVerification(true);
    setVerificationMessage("");
    setVerificationError(false);
    try {
      setVerificationMessage((await api.resendVerification()).message);
      setRegistrationNotice("");
      setCooldownSeconds(60);
    } catch (error) {
      setVerificationError(true);
      if (error instanceof ApiError && error.status === 429 && error.retryAfterSeconds) {
        setCooldownSeconds(error.retryAfterSeconds);
      }
      setVerificationMessage(error instanceof Error ? error.message : "Não foi possível enviar agora.");
    } finally {
      verificationRequestInFlight.current = false;
      setSendingVerification(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-body">
        <header className="mobile-header">
          <div className="mobile-brand">
            <PiggyBank aria-hidden="true" size={21} />
            <strong>Nivra</strong>
            <AlphaBadge />
          </div>
          <button aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"} className="icon-button mobile-theme-button" onClick={toggleTheme} type="button">
            {theme === "dark" ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
          </button>
        </header>
        {user && !user.email_verificado ? (
          <aside className="verification-banner" role={verificationError ? "alert" : "status"}>
            <span><strong>Confirme seu e-mail.</strong> {registrationNotice || "Isso protege a recuperação da sua conta."}</span>
            <button disabled={sendingVerification || cooldownSeconds > 0} onClick={resendVerification} type="button">
              {sendingVerification ? "Enviando..." : cooldownSeconds > 0 ? `Tentar novamente em ${cooldownSeconds}s` : "Reenviar e-mail"}
            </button>
            {verificationMessage ? <small className={verificationError ? "verification-error" : "verification-success"}>{verificationMessage}</small> : null}
          </aside>
        ) : null}
        <main className="main-content">
          <Outlet />
        </main>
      </div>
      <MobileNavigation />
    </div>
  );
}
