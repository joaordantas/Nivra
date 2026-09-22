import { LogOut, Moon, Sun } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth, useTheme } from "../../app/providers";
import { primaryNavigation, productIcon as ProductIcon, secondaryNavigation } from "./navigation";
import { AlphaBadge } from "./AlphaBadge";

function NavigationLink({ item }: { item: (typeof primaryNavigation)[number] }) {
  const Icon = item.icon;

  return (
    <NavLink
      className={({ isActive }) => `sidebar-link${isActive ? " is-active" : ""}`}
      to={item.path}
    >
      <Icon aria-hidden="true" size={19} strokeWidth={1.9} />
      <span>{item.label}</span>
    </NavLink>
  );
}

export function Sidebar() {
  const { logout, user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="desktop-sidebar">
      <div className="product-brand">
        <span className="product-mark">
          <ProductIcon aria-hidden="true" size={23} strokeWidth={2} />
        </span>
        <span>
          <strong>Nivra</strong>
          <small>Seu dinheiro, mais claro</small>
        </span>
        <AlphaBadge />
      </div>

      <nav aria-label="Navegação principal" className="sidebar-navigation">
        <p className="navigation-label">Menu</p>
        {primaryNavigation.map((item) => (
          <NavigationLink item={item} key={item.path} />
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="theme-button" onClick={toggleTheme} type="button">
          {theme === "dark" ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
          <span>{theme === "dark" ? "Tema claro" : "Tema escuro"}</span>
        </button>
        <nav aria-label="Navegação secundária">
          {secondaryNavigation.map((item) => (
            <NavigationLink item={item} key={item.path} />
          ))}
        </nav>

        <div className="sidebar-user">
          <span className="user-avatar" aria-hidden="true">
            {user?.usuario.slice(0, 1).toUpperCase()}
          </span>
          <span className="user-details">
            <strong>{user?.usuario}</strong>
            <small>{user?.email}</small>
          </span>
          <button aria-label="Sair" className="icon-button" onClick={logout} title="Sair" type="button">
            <LogOut aria-hidden="true" size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}
