import type {
  Account,
  AccountType,
  Card,
  CardPurchase,
  Category,
  ClientInstallmentsResponse,
  Invoice,
  InvoiceDetail,
  OpenFinanceConnection,
  OpenFinanceAccountLink,
  OpenFinanceExternalAccount,
  OpenFinanceSyncResult,
  ProfitSummary,
  ReceivableByClient,
  Sale,
  Transaction,
  TransactionSummary,
  Transfer,
  User,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${API_URL}/api/auth/csrf`, { credentials: "include" });
  if (!response.ok) throw new Error("Não foi possível iniciar uma conexão segura.");
  const body = await response.json() as { csrf_token: string };
  csrfToken = body.csrf_token;
  return csrfToken;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? "GET").toUpperCase();
  const headers = new Headers(options?.headers);
  headers.set("Content-Type", "application/json");
  if (UNSAFE_METHODS.has(method)) headers.set("X-CSRF-Token", await getCsrfToken());

  const response = await fetch(`${API_URL}/api${path}`, {
    ...options,
    method,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let detail = "Erro ao se comunicar com a API.";
    try {
      const body: { detail?: unknown } = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        const messages = body.detail
          .map((item) => {
            if (typeof item === "string") return item;
            if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") return item.msg;
            return null;
          })
          .filter((message): message is string => Boolean(message));
        if (messages.length > 0) detail = messages.join(" ");
      }
    } catch {
      detail = response.statusText || detail;
    }
    if (response.status === 401) window.dispatchEvent(new Event("nivra:unauthorized"));
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  getCurrentUser: () => request<User>("/auth/me"),

  login: (email: string, senha: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) }),

  register: (payload: { usuario: string; email: string; senha: string; tipo_perfil: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/email/verify", { method: "POST", body: JSON.stringify({ token }) }),
  resendVerification: () =>
    request<{ message: string }>("/auth/email/resend", { method: "POST" }),
  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/password/forgot", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, novaSenha: string, confirmarSenha: string) =>
    request<{ message: string }>("/auth/password/reset", {
      method: "POST",
      body: JSON.stringify({ token, nova_senha: novaSenha, confirmar_senha: confirmarSenha }),
    }),
  changePassword: (senhaAtual: string, novaSenha: string, confirmarSenha: string) =>
    request<{ message: string }>("/auth/password/change", {
      method: "POST",
      body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: novaSenha, confirmar_senha: confirmarSenha }),
    }),

  logout: async () => {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } finally {
      csrfToken = null;
    }
  },

  getCategories: () => request<Category[]>("/categories"),
  createCategory: (nome: string) => request<Category>("/categories", { method: "POST", body: JSON.stringify({ nome }) }),
  updateCategory: (categoriaId: number, nome: string) => request<Category>(`/categories/${categoriaId}`, { method: "PUT", body: JSON.stringify({ nome }) }),
  deleteCategory: (categoriaId: number) => request<void>(`/categories/${categoriaId}`, { method: "DELETE" }),

  getTransactions: () => request<Transaction[]>("/transactions"),
  getTransactionSummary: () => request<TransactionSummary>("/transactions/summary"),
  createTransaction: (payload: { valor: number; tipo: "entrada" | "saida"; categoria_id: number | null; comentario: string; data: string; conta_id: number | null }) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(payload) }),
  updateTransaction: (transactionId: number, payload: { valor: number; tipo: "entrada" | "saida"; categoria_id: number | null; comentario: string; data: string; conta_id: number | null }) =>
    request<Transaction>(`/transactions/${transactionId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTransaction: (transactionId: number) => request<void>(`/transactions/${transactionId}`, { method: "DELETE" }),

  getAccounts: (includeInactive = false) => request<Account[]>(`/accounts?incluir_inativas=${includeInactive}`),
  createAccount: (payload: { nome: string; tipo: AccountType; saldo_inicial: number }) =>
    request<Account>("/accounts", { method: "POST", body: JSON.stringify(payload) }),
  updateAccount: (accountId: number, payload: { nome: string; tipo: AccountType; saldo_inicial: number }) =>
    request<Account>(`/accounts/${accountId}`, { method: "PUT", body: JSON.stringify(payload) }),
  updateAccountStatus: (accountId: number, ativo: boolean) =>
    request<Account>(`/accounts/${accountId}/status`, { method: "PATCH", body: JSON.stringify({ ativo }) }),
  setPrimaryAccount: (accountId: number) => request<Account>(`/accounts/${accountId}/primary`, { method: "PATCH" }),
  createOpenFinanceConnectToken: () =>
    request<{ connect_token: string; provider: "pluggy"; environment: "sandbox" }>("/open-finance/connect-token", { method: "POST" }),
  completeOpenFinanceConnection: (itemId: string) =>
    request<OpenFinanceConnection>("/open-finance/connections/complete", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId }),
    }),
  getOpenFinanceConnections: () =>
    request<OpenFinanceConnection[]>("/open-finance/connections"),
  syncOpenFinanceConnection: (connectionId: number) =>
    request<OpenFinanceSyncResult>(`/open-finance/connections/${connectionId}/sync`, {
      method: "POST",
    }),
  getOpenFinanceExternalAccounts: (connectionId: number) =>
    request<OpenFinanceExternalAccount[]>(`/open-finance/connections/${connectionId}/accounts`),
  linkOpenFinanceExternalAccount: (externalAccountId: number, accountId: number) =>
    request<OpenFinanceAccountLink>(`/open-finance/external-accounts/${externalAccountId}/link`, {
      method: "PATCH",
      body: JSON.stringify({ conta_nivra_id: accountId }),
    }),
  createAccountFromOpenFinance: (externalAccountId: number) =>
    request<OpenFinanceAccountLink>(`/open-finance/external-accounts/${externalAccountId}/nivra-account`, {
      method: "POST",
    }),

  getTransfers: () => request<Transfer[]>("/transfers"),
  createTransfer: (payload: { conta_origem_id: number; conta_destino_id: number; valor: number; descricao: string; data: string }) =>
    request<Transfer>("/transfers", { method: "POST", body: JSON.stringify(payload) }),
  updateTransfer: (transferId: number, payload: { conta_origem_id: number; conta_destino_id: number; valor: number; descricao: string; data: string }) =>
    request<Transfer>(`/transfers/${transferId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTransfer: (transferId: number) => request<void>(`/transfers/${transferId}`, { method: "DELETE" }),

  getCards: (includeInactive = true) => request<Card[]>(`/cards?incluir_inativos=${includeInactive}`),
  createCard: (payload: { nome: string; limite_total: number; dia_fechamento: number; dia_vencimento: number }) =>
    request<Card>("/cards", { method: "POST", body: JSON.stringify(payload) }),
  updateCard: (cardId: number, payload: { nome: string; limite_total: number; dia_fechamento: number; dia_vencimento: number }) =>
    request<Card>(`/cards/${cardId}`, { method: "PUT", body: JSON.stringify(payload) }),
  updateCardStatus: (cardId: number, ativo: boolean) =>
    request<Card>(`/cards/${cardId}/status`, { method: "PATCH", body: JSON.stringify({ ativo }) }),
  getCardInvoices: (cardId: number) => request<Invoice[]>(`/cards/${cardId}/invoices`),
  getInvoice: (invoiceId: number) => request<InvoiceDetail>(`/invoices/${invoiceId}`),
  createCardPurchase: (payload: { cartao_id: number; valor: number; descricao: string; categoria_id: number | null; data: string }) =>
    request<CardPurchase>("/card-purchases", { method: "POST", body: JSON.stringify(payload) }),
  updateCardPurchase: (purchaseId: number, payload: { cartao_id: number; valor: number; descricao: string; categoria_id: number | null; data: string }) =>
    request<CardPurchase>(`/card-purchases/${purchaseId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCardPurchase: (purchaseId: number) => request<void>(`/card-purchases/${purchaseId}`, { method: "DELETE" }),
  payInvoice: (invoiceId: number, accountId: number, paymentDate: string) =>
    request<InvoiceDetail>(`/invoices/${invoiceId}/pay`, { method: "POST", body: JSON.stringify({ conta_id: accountId, data: paymentDate }) }),

  getProfit: (dataInicio: string, dataFim: string) =>
    request<ProfitSummary>(`/dashboard/profit?data_inicio=${dataInicio}&data_fim=${dataFim}`),
  getReceivablesTotal: () => request<{ total: number }>("/dashboard/receivables/total"),
  getReceivablesByClient: () => request<ReceivableByClient[]>("/dashboard/receivables/by-client"),

  getSales: () => request<Sale[]>("/sales"),
  createSale: (payload: { cliente: string; tipo: string; valor_total: number; comentario: string; data: string }) =>
    request<Sale>("/sales", { method: "POST", body: JSON.stringify(payload) }),
  getClients: () => request<string[]>("/sales/clients"),
  getInstallmentsByClient: (cliente: string) => request<ClientInstallmentsResponse>(`/installments/by-client?cliente=${encodeURIComponent(cliente)}`),
  createInstallments: (payload: { venda_id: number; quantidade: number; valor: number; status: "pendente" | "pago"; data: string }) =>
    request("/installments", { method: "POST", body: JSON.stringify(payload) }),
  payInstallment: (parcelaId: number) => request<{ message: string }>(`/installments/${parcelaId}/pay`, { method: "POST" }),
};
