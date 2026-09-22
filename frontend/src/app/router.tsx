import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { AppLayout } from "../components/layout/AppLayout";
import { ComingSoonPage } from "../pages/ComingSoonPage";
import { CardsPage } from "../pages/CardsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage } from "../pages/LoginPage";
import { LumiPage } from "../pages/LumiPage";
import { InstallmentsPage } from "../pages/InstallmentsPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { SettingsPage } from "../pages/SettingsPage";
import { CategoriesPage } from "../pages/settings/CategoriesPage";
import { TransactionsPage } from "../pages/TransactionsPage";
import { AccountsPage } from "../pages/AccountsPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import { VerifyEmailPage } from "../pages/VerifyEmailPage";
import { SecurityPage } from "../pages/settings/SecurityPage";
import { useAuth } from "./providers";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="route-loading" role="status">Verificando sua sessão...</div>;
  return isAuthenticated ? children : <Navigate replace to="/login" />;
}

function PublicRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="route-loading" role="status">Verificando sua sessão...</div>;
  return isAuthenticated ? <Navigate replace to="/dashboard" /> : children;
}

const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <PublicRoute>
        <LoginPage />
      </PublicRoute>
    ),
  },
  { path: "/forgot-password", element: <PublicRoute><ForgotPasswordPage /></PublicRoute> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate replace to="/dashboard" /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "transactions", element: <TransactionsPage /> },
      { path: "installments", element: <InstallmentsPage /> },
      { path: "accounts", element: <AccountsPage /> },
      { path: "cards", element: <CardsPage /> },
      {
        path: "budgets",
        element: <ComingSoonPage description="Os orçamentos por categoria serão adicionados na etapa de planejamento." title="Orçamentos" />,
      },
      {
        path: "goals",
        element: <ComingSoonPage description="As metas financeiras serão adicionadas depois do núcleo financeiro." title="Metas" />,
      },
      { path: "lumi", element: <LumiPage /> },
      { path: "assistant", element: <Navigate replace to="/lumi" /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "settings/categories", element: <CategoriesPage /> },
      { path: "settings/security", element: <SecurityPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
