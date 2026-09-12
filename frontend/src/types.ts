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
