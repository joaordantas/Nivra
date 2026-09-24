import type {
  Account,
  AccountType,
  Card,
  CardPurchase,
  Category,
  ClientInstallmentsResponse,
  Invoice,
  InvoiceDetail,
  FinancialInsights,
  InstallmentPlanDetail,
  InstallmentPlanSummary,
  InstallmentPlanUpdate,
  LumiHistoryMessage,
  LumiActionConfirmationResponse,
  LumiResponse,
  OpenFinanceConnection,
  OpenFinanceAccountLink,
  OpenFinanceExternalAccount,
  OpenFinanceSyncResult,
  ProfitSummary,
  ReconciliationResult,
  ReconciliationSuggestion,
  ReconciliationBatchResult,
  ReceivableByClient,
  Sale,
  Transaction,
  TransactionSummary,
  Transfer,
  User,
} from "../types";

const localApiUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? localApiUrl : "");
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;

  constructor(message: string, status: number, retryAfterSeconds: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const retryAt = Date.parse(value);
  if (Number.isNaN(retryAt)) return null;
  return Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
}

async function apiErrorFromResponse(response: Response, fallback: string): Promise<ApiError> {
  let detail = fallback;
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
  return new ApiError(detail, response.status, parseRetryAfter(response.headers.get("Retry-After")));
}

async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${API_URL}/api/auth/csrf`, { credentials: "include" });
  if (!response.ok) throw await apiErrorFromResponse(response, "Não foi possível iniciar uma conexão segura.");
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
    if (response.status === 401) window.dispatchEvent(new Event("nivra:unauthorized"));
    throw await apiErrorFromResponse(response, "Erro ao se comunicar com a API.");
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

  getTransactions: (dataInicio?: string, dataFim?: string) => {
    const params = new URLSearchParams();
    if (dataInicio) params.set("data_inicio", dataInicio);
    if (dataFim) params.set("data_fim", dataFim);
    const query = params.size ? `?${params.toString()}` : "";
    return request<Transaction[]>(`/transactions${query}`);
  },
  getTransactionSummary: () => request<TransactionSummary>("/transactions/summary"),
  createTransaction: (payload: { valor: number; tipo: "entrada" | "saida"; categoria_id: number | null; comentario: string; data: string; conta_id: number | null }) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(payload) }),
  updateTransaction: (transactionId: number, payload: { valor: number; tipo: "entrada" | "saida"; categoria_id: number | null; comentario: string; data: string; conta_id: number | null }) =>
    request<Transaction>(`/transactions/${transactionId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTransaction: (transactionId: number) => request<void>(`/transactions/${transactionId}`, { method: "DELETE" }),
  getInstallmentPlans: () => request<InstallmentPlanSummary[]>("/installment-plans"),
  getInstallmentPlan: (installmentPlanId: number) =>
    request<InstallmentPlanDetail>(`/installment-plans/${installmentPlanId}`),
  createInstallmentPlan: (payload: {
    descricao: string;
    valor_total: number;
    quantidade_parcelas: number;
    data_inicial: string;
    tipo: "entrada" | "saida";
    categoria_id: number | null;
    conta_id: number | null;
  }) => request<InstallmentPlanDetail>("/installment-plans", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  updateInstallmentPlan: (installmentPlanId: number, payload: InstallmentPlanUpdate) =>
    request<InstallmentPlanDetail>(`/installment-plans/${installmentPlanId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteInstallmentPlan: (installmentPlanId: number) =>
    request<void>(`/installment-plans/${installmentPlanId}`, { method: "DELETE" }),
  confirmBankReconciliation: (bankTransactionId: number) =>
    request<ReconciliationResult>(`/transactions/bank/${bankTransactionId}/reconciliation/confirm`, { method: "POST" }),
  rejectBankReconciliation: (bankTransactionId: number) =>
    request<ReconciliationResult>(`/transactions/bank/${bankTransactionId}/reconciliation/reject`, { method: "POST" }),
  getReconciliationSuggestions: () =>
    request<ReconciliationSuggestion[]>("/transactions/reconciliation/suggestions"),
  confirmSelectedBankReconciliation: (bankTransactionId: number, transactionId: number) =>
    request<ReconciliationResult>(`/transactions/bank/${bankTransactionId}/reconciliation/${transactionId}/confirm`, { method: "POST" }),
  rejectSelectedBankReconciliation: (bankTransactionId: number, transactionId: number) =>
    request<ReconciliationResult>(`/transactions/bank/${bankTransactionId}/reconciliation/${transactionId}/reject`, { method: "POST" }),
  confirmHighConfidenceReconciliations: () =>
    request<ReconciliationBatchResult>("/transactions/reconciliation/confirm-high-confidence", { method: "POST" }),

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
  getInsights: (dataInicio: string, dataFim: string) =>
    request<FinancialInsights>(`/insights?data_inicio=${dataInicio}&data_fim=${dataFim}`),
  getLumiCapabilities: () => request<{ public_enabled: boolean }>("/lumi/capabilities"),
  sendLumiMessage: (message: string, history: LumiHistoryMessage[], signal?: AbortSignal) =>
    request<LumiResponse>("/lumi/message", {
      method: "POST",
      body: JSON.stringify({ message, history }),
      signal,
    }),
  confirmLumiAction: (confirmationId: string) =>
    request<LumiActionConfirmationResponse>("/lumi/actions/confirm", {
      method: "POST", body: JSON.stringify({ confirmation_id: confirmationId }),
    }),
  cancelLumiAction: (confirmationId: string) =>
    request<LumiActionConfirmationResponse>("/lumi/actions/cancel", {
      method: "POST", body: JSON.stringify({ confirmation_id: confirmationId }),
    }),
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
