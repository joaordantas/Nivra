export interface User {
  id: number;
  usuario: string;
  email: string;
  tipo_perfil: string;
  email_verificado: boolean;
  email_verificado_em: string | null;
}

export interface Category {
  id: number;
  nome: string;
  padrao: boolean;
}

export interface Transaction {
  id: number;
  valor: number;
  tipo: "entrada" | "saida";
  categoria_id: number | null;
  categoria: string;
  comentario: string | null;
  data: string;
  conta_id: number | null;
  conta: string;
  origem: "manual" | "open_finance";
  editavel: boolean;
  status_conciliacao: "pendente" | "possivel_correspondencia" | "ambigua" | "conciliada" | "ignorada" | "reaberta" | null;
  transacao_nivra_id: number | null;
  conciliada_com_banco: boolean;
  neutra: boolean;
  instituicao_nome: string | null;
  ultima_sincronizacao_em: string | null;
  parcelamento_id: number | null;
  numero_parcela: number | null;
  quantidade_parcelas: number | null;
}

export type InstallmentTemporalStatus = "data_atingida" | "futura";

export interface InstallmentPlanInstallment {
  id: number;
  numero_parcela: number;
  quantidade_parcelas: number;
  valor: number;
  data: string;
  tipo: "entrada" | "saida";
  categoria_id: number | null;
  categoria: string;
  conta_id: number | null;
  conta: string;
  comentario: string | null;
  status_temporal: InstallmentTemporalStatus;
}

export interface InstallmentPlanSummary {
  id: number;
  descricao: string;
  valor_total: number;
  quantidade_parcelas: number;
  data_inicial: string;
  criado_em: string;
  atualizado_em: string;
  parcelas_persistidas: number;
  valor_persistido: number;
  primeira_parcela_data: string;
  ultima_parcela_data: string;
  parcelas_com_data_atingida: number;
  parcelas_futuras: number;
  proxima_parcela_data: string | null;
}

export interface InstallmentPlanDetail extends InstallmentPlanSummary {
  parcelas: InstallmentPlanInstallment[];
}

export interface InstallmentPlanUpdate {
  descricao: string;
  categoria_id: number | null;
  conta_id: number | null;
}

export interface ReconciliationResult {
  transacao_bancaria_id: number;
  transacao_nivra_id: number | null;
  status: "conciliada" | "rejeitada";
}

export interface ReconciliationCandidate {
  transacao_nivra_id: number;
  descricao: string;
  valor: number;
  data: string;
  direcao: "entrada" | "saida";
  confianca: "alta" | "media" | "baixa";
  motivos: string[];
}

export interface ReconciliationSuggestion {
  transacao_bancaria_id: number;
  descricao: string;
  valor: number;
  data: string;
  direcao: "entrada" | "saida";
  conta_id: number;
  conta: string;
  instituicao_nome: string;
  ambigua: boolean;
  candidatos: ReconciliationCandidate[];
}

export interface ReconciliationBatchResult {
  confirmadas: number;
  solicitadas: number;
}

export type AccountType = "corrente" | "poupanca" | "digital" | "dinheiro" | "outro";

export interface Account {
  id: number;
  nome: string;
  tipo: AccountType;
  saldo_inicial: number;
  saldo_atual: number;
  ativo: boolean;
  principal: boolean;
  percentual_uso: number;
  mais_utilizada: boolean;
  origem: "manual" | "open_finance";
  conta_externa_id: number | null;
  instituicao_nome: string | null;
  ultima_sincronizacao_em: string | null;
}

export interface OpenFinanceConnection {
  id: number;
  provider: "pluggy";
  instituicao_nome: string;
  status: string;
  ambiente: "sandbox" | "production";
  criada_em: string;
  atualizada_em: string;
  ultima_sincronizacao_em: string | null;
  desconectada_em: string | null;
  ultimo_evento_status: string | null;
  ultimo_erro: string | null;
}

export interface OpenFinanceExternalAccount {
  id: number;
  nome: string;
  tipo: string;
  subtipo: string | null;
  moeda: string;
  saldo: number | null;
  quantidade_transacoes: number;
  conta_nivra_id: number | null;
  conta_nivra_nome: string | null;
  pode_vincular_conta_nivra: boolean;
}

export interface OpenFinanceAccountLink {
  conta_externa_id: number;
  conta_nivra_id: number;
  conta_nivra_nome: string;
}

export interface OpenFinanceSyncResult {
  conexao_id: number;
  contas_criadas: number;
  contas_atualizadas: number;
  contas_removidas: number;
  transacoes_criadas: number;
  transacoes_atualizadas: number;
  transacoes_removidas: number;
  transacoes_processadas: number;
}

export type InvoiceStatus = "aberta" | "fechada" | "paga" | "vencida";

export interface Invoice {
  id: number;
  cartao_id: number;
  cartao: string;
  ano_referencia: number;
  mes_referencia: number;
  data_inicio: string;
  data_fechamento: string;
  data_vencimento: string;
  valor_total: number;
  valor_pago: number;
  status: InvoiceStatus;
  data_pagamento: string | null;
  conta_pagamento_id: number | null;
  conta_pagamento: string | null;
  quantidade_compras: number;
}

export interface Card {
  id: number;
  nome: string;
  limite_total: number;
  limite_utilizado: number;
  limite_disponivel: number;
  percentual_utilizado: number;
  dia_fechamento: number;
  dia_vencimento: number;
  ativo: boolean;
  fatura_atual: Invoice | null;
}

export interface CardPurchase {
  id: number;
  cartao_id: number;
  cartao: string;
  fatura_id: number;
  valor: number;
  descricao: string;
  categoria_id: number | null;
  categoria: string;
  data: string;
}

export interface InvoiceDetail extends Invoice {
  compras: CardPurchase[];
}

export interface CardFormValues {
  nome: string;
  limiteTotal: number;
  diaFechamento: number;
  diaVencimento: number;
}

export interface CardPurchaseFormValues {
  cartaoId: number;
  valor: number;
  descricao: string;
  categoriaId: number | null;
  data: string;
}

export interface Transfer {
  id: number;
  conta_origem_id: number;
  conta_origem: string;
  conta_destino_id: number;
  conta_destino: string;
  valor: number;
  descricao: string | null;
  data: string;
}

export type MovementType = "entrada" | "saida" | "transferencia";

export interface MovementFormValues {
  tipo: MovementType;
  valor: number;
  descricao: string;
  data: string;
  categoriaId: number | null;
  contaId: number | null;
  contaOrigemId: number;
  contaDestinoId: number;
  forma: "avista" | "parcelado";
  quantidadeParcelas: number;
}

export interface TransactionSummary {
  entradas: number;
  saidas: number;
  saldo: number;
}

export interface ProfitSummary {
  entrada: number;
  saida: number;
  lucro: number;
}

export interface ReceivableByClient {
  cliente: string;
  valor_pendente: number;
}

export interface Sale {
  id: number;
  cliente: string;
  tipo: string;
  valor_total: number;
  comentario: string | null;
  data: string;
}

export interface Installment {
  id: number;
  venda_id: number;
  valor: number;
  status: string;
  data: string;
}

export interface ClientInstallmentsResponse {
  cliente: string;
  parcelas: Installment[];
  resumo: {
    total_pago: number;
    valor_total_vendas: number;
    ainda_falta: number;
  };
}
