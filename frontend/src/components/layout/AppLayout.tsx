import { Moon, PiggyBank, Sun } from "lucide-react";
import { Outlet } from "react-router-dom";

import { MobileNavigation } from "./MobileNavigation";
import { AlphaBadge } from "./AlphaBadge";
import { Sidebar } from "./Sidebar";
import { useTheme } from "../../app/providers";
import { useAuth } from "../../app/providers";
import { useState } from "react";
import { api } from "../../services/api";

export function AppLayout() {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();
  const [verificationMessage, setVerificationMessage] = useState("");
  const [sendingVerification, setSendingVerification] = useState(false);

  async function resendVerification() {
    setSendingVerification(true);
    try {
      setVerificationMessage((await api.resendVerification()).message);
    } catch (error) {
      setVerificationMessage(error instanceof Error ? error.message : "Não foi possível enviar agora.");
    } finally {
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
          <aside className="verification-banner" role="status">
            <span><strong>Confirme seu e-mail.</strong> Isso protege a recuperação da sua conta.</span>
            <button disabled={sendingVerification} onClick={resendVerification} type="button">{sendingVerification ? "Enviando..." : "Reenviar e-mail"}</button>
            {verificationMessage ? <small>{verificationMessage}</small> : null}
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
