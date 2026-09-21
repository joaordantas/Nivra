import { LogOut, MoreHorizontal, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../../app/providers";
import { mobileMoreFinanceNavigation, mobileMoreSettingsNavigation, mobileNavigation } from "./navigation";

function matchesLocation(path: string, pathname: string, hash: string) {
  const [basePath, anchor] = path.split("#");
  const matchesPath = pathname === basePath || pathname.startsWith(`${basePath}/`);
  return matchesPath && (!anchor || hash === `#${anchor}`);
}

export function MobileNavigation() {
  const { logout, user } = useAuth();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const moreIsActive = [...mobileMoreFinanceNavigation, ...mobileMoreSettingsNavigation]
    .some((item) => matchesLocation(item.path, location.pathname, location.hash));

  useEffect(() => {
    setMoreOpen(false);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    if (!moreOpen) return;

    closeButtonRef.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMoreOpen(false);
        requestAnimationFrame(() => moreButtonRef.current?.focus());
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    document.body.classList.add("mobile-menu-open");
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.body.classList.remove("mobile-menu-open");
    };
  }, [moreOpen]);

  return (
    <>
      {moreOpen ? (
        <>
          <button aria-label="Fechar menu Mais" className="mobile-more-backdrop" onClick={() => setMoreOpen(false)} type="button" />
          <section aria-labelledby="mobile-more-title" aria-modal="true" className="mobile-more-sheet" role="dialog">
            <header className="mobile-more-header">
              <h2 id="mobile-more-title">Mais</h2>
              <button aria-label="Fechar menu Mais" className="icon-button" onClick={() => setMoreOpen(false)} ref={closeButtonRef} type="button">
                <X aria-hidden="true" size={20} />
              </button>
            </header>

            <nav aria-label="Finanças" className="mobile-more-group">
              <span className="navigation-label">Finanças</span>
              {mobileMoreFinanceNavigation.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink className={`mobile-more-link${matchesLocation(item.path, location.pathname, location.hash) ? " is-active" : ""}`} key={item.path} onClick={() => setMoreOpen(false)} to={item.path}>
                    <Icon aria-hidden="true" size={20} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            <nav aria-label="Configurações" className="mobile-more-group">
              <span className="navigation-label">Configurações</span>
              {mobileMoreSettingsNavigation.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink className={`mobile-more-link${matchesLocation(item.path, location.pathname, location.hash) ? " is-active" : ""}`} key={item.path} onClick={() => setMoreOpen(false)} to={item.path}>
                    <Icon aria-hidden="true" size={20} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            <section aria-label="Conta" className="mobile-account-section">
              <span className="navigation-label">Conta</span>
              <div className="mobile-account-user">
                <span aria-hidden="true" className="user-avatar">
                  {user?.usuario.slice(0, 1).toUpperCase()}
                </span>
                <span className="user-details">
                  <strong>{user?.usuario}</strong>
                  <small>{user?.email}</small>
                </span>
              </div>
              <button className="mobile-logout-button" onClick={logout} type="button">
                <LogOut aria-hidden="true" size={19} />
                <span>Sair da conta</span>
              </button>
            </section>
          </section>
        </>
      ) : null}

      <nav aria-label="Navegação mobile" className="mobile-navigation">
        {mobileNavigation.slice(0, 2).map((item) => {
          const Icon = item.icon;
          return (
            <NavLink className={({ isActive }) => `mobile-nav-link${isActive ? " is-active" : ""}`} key={item.path} to={item.path}>
              <Icon aria-hidden="true" size={21} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}

        <span aria-hidden="true" className="mobile-nav-spacer" />
        <NavLink aria-label="Adicionar transação" className="mobile-add-button" to="/transactions?new=1#new-transaction">
          <Plus aria-hidden="true" size={27} strokeWidth={2.2} />
        </NavLink>

        {mobileNavigation.slice(2).map((item) => {
          const Icon = item.icon;
          return (
            <NavLink className={({ isActive }) => `mobile-nav-link${isActive ? " is-active" : ""}`} key={item.path} to={item.path}>
              <Icon aria-hidden="true" size={21} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}

        <button aria-expanded={moreOpen} aria-haspopup="dialog" className={`mobile-nav-link mobile-nav-more-button${moreIsActive || moreOpen ? " is-active" : ""}`} onClick={() => setMoreOpen((open) => !open)} ref={moreButtonRef} type="button">
          <MoreHorizontal aria-hidden="true" size={21} />
          <span>Mais</span>
        </button>
      </nav>
    </>
  );
}
