from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    func,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()
money = Numeric(14, 2)

usuarios = Table(
    "usuarios", metadata,
    Column("id", Integer, primary_key=True),
    Column("usuario", String(120), nullable=False, unique=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("senha", Text, nullable=False),
    Column("tipo_perfil", String(80), nullable=False, server_default="Apenas Financeiro"),
    Column("email_verificado", Boolean, nullable=False, server_default=false()),
    Column("email_verificado_em", DateTime(timezone=True)),
)

sessoes = Table(
    "sessoes", metadata,
    Column("id", Integer, primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("csrf_hash", String(64), nullable=False),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expira_em", DateTime(timezone=True), nullable=False),
    Column("revogada_em", DateTime(timezone=True)),
)
Index("ix_sessoes_usuario", sessoes.c.usuario_id)
Index("ix_sessoes_expiracao", sessoes.c.expira_em)

auth_tokens = Table(
    "auth_tokens", metadata,
    Column("id", Integer, primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
    Column("finalidade", String(32), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("criado_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expira_em", DateTime(timezone=True), nullable=False),
    Column("usado_em", DateTime(timezone=True)),
    Column("revogado_em", DateTime(timezone=True)),
    CheckConstraint(
        "finalidade IN ('email_verification', 'password_reset')",
        name="ck_auth_tokens_finalidade",
    ),
)
Index("ix_auth_tokens_usuario_finalidade", auth_tokens.c.usuario_id, auth_tokens.c.finalidade)
Index("ix_auth_tokens_expiracao", auth_tokens.c.expira_em)

auth_rate_events = Table(
    "auth_rate_events", metadata,
    Column("id", Integer, primary_key=True),
    Column("escopo", String(40), nullable=False),
    Column("sujeito_hash", String(64), nullable=False),
    Column("criado_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
Index(
    "ix_auth_rate_events_lookup",
    auth_rate_events.c.escopo,
    auth_rate_events.c.sujeito_hash,
    auth_rate_events.c.criado_em,
)

categorias = Table(
    "categorias", metadata,
    Column("id", Integer, primary_key=True),
    Column("nome", String(120), nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    Column("chave_sistema", String(50)),
    UniqueConstraint("usuario_id", "chave_sistema", name="uq_categorias_usuario_chave_sistema"),
)

contas = Table(
    "contas", metadata,
    Column("id", Integer, primary_key=True),
    Column("nome", String(80), nullable=False),
    Column("tipo", String(30), nullable=False, server_default="digital"),
    Column("saldo_inicial", money, nullable=False, server_default="0"),
    Column("ativo", Boolean, nullable=False, server_default=true()),
    Column("principal", Boolean, nullable=False, server_default=false()),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    UniqueConstraint("nome", "usuario_id", name="uq_contas_nome_usuario"),
)
Index("ix_contas_usuario", contas.c.usuario_id)
Index(
    "uq_contas_principal_usuario", contas.c.usuario_id, unique=True,
    postgresql_where=and_(contas.c.principal.is_(True), contas.c.ativo.is_(True)),
    sqlite_where=and_(contas.c.principal.is_(True), contas.c.ativo.is_(True)),
)

transacoes = Table(
    "transacoes", metadata,
    Column("id", Integer, primary_key=True),
    Column("valor", money, nullable=False),
    Column("tipo", String(10), nullable=False),
    Column("categoria_id", ForeignKey("categorias.id")),
    Column("conta_id", ForeignKey("contas.id")),
    Column("comentario", Text),
    Column("data", Date, nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    CheckConstraint("valor > 0", name="ck_transacoes_valor_positivo"),
    CheckConstraint("tipo IN ('entrada', 'saida')", name="ck_transacoes_tipo"),
)
Index("ix_transacoes_usuario_data", transacoes.c.usuario_id, transacoes.c.data)
Index("ix_transacoes_conta", transacoes.c.conta_id)
Index("ix_transacoes_categoria", transacoes.c.categoria_id)

transferencias = Table(
    "transferencias", metadata,
    Column("id", Integer, primary_key=True),
    Column("conta_origem_id", ForeignKey("contas.id"), nullable=False),
    Column("conta_destino_id", ForeignKey("contas.id"), nullable=False),
    Column("valor", money, nullable=False),
    Column("descricao", Text),
    Column("data", Date, nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    CheckConstraint("valor > 0", name="ck_transferencias_valor_positivo"),
    CheckConstraint("conta_origem_id <> conta_destino_id", name="ck_transferencias_contas_distintas"),
)
Index("ix_transferencias_usuario_data", transferencias.c.usuario_id, transferencias.c.data)

cartoes = Table(
    "cartoes", metadata,
    Column("id", Integer, primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    Column("nome", String(60), nullable=False),
    Column("limite_total", money, nullable=False),
    Column("dia_fechamento", Integer, nullable=False),
    Column("dia_vencimento", Integer, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=true()),
    Column("criado_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("atualizado_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("nome", "usuario_id", name="uq_cartoes_nome_usuario"),
    CheckConstraint("limite_total > 0", name="ck_cartoes_limite_positivo"),
    CheckConstraint("dia_fechamento BETWEEN 1 AND 31", name="ck_cartoes_fechamento"),
    CheckConstraint("dia_vencimento BETWEEN 1 AND 31", name="ck_cartoes_vencimento"),
)
Index("ix_cartoes_usuario", cartoes.c.usuario_id)

faturas = Table(
    "faturas", metadata,
    Column("id", Integer, primary_key=True),
    Column("cartao_id", ForeignKey("cartoes.id"), nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    Column("ano_referencia", Integer, nullable=False),
    Column("mes_referencia", Integer, nullable=False),
    Column("data_inicio", Date, nullable=False),
    Column("data_fechamento", Date, nullable=False),
    Column("data_vencimento", Date, nullable=False),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("cartao_id", "ano_referencia", "mes_referencia", name="uq_faturas_cartao_periodo"),
    CheckConstraint("mes_referencia BETWEEN 1 AND 12", name="ck_faturas_mes"),
)
Index("ix_faturas_cartao_periodo", faturas.c.cartao_id, faturas.c.ano_referencia, faturas.c.mes_referencia)

compras_cartao = Table(
    "compras_cartao", metadata,
    Column("id", Integer, primary_key=True),
    Column("cartao_id", ForeignKey("cartoes.id"), nullable=False),
    Column("fatura_id", ForeignKey("faturas.id"), nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    Column("categoria_id", ForeignKey("categorias.id")),
    Column("valor", money, nullable=False),
    Column("descricao", Text, nullable=False),
    Column("data", Date, nullable=False),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("atualizada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("valor > 0", name="ck_compras_cartao_valor_positivo"),
)
Index("ix_compras_cartao_fatura", compras_cartao.c.fatura_id)
Index("ix_compras_cartao_usuario_data", compras_cartao.c.usuario_id, compras_cartao.c.data)

pagamentos_fatura = Table(
    "pagamentos_fatura", metadata,
    Column("id", Integer, primary_key=True),
    Column("fatura_id", ForeignKey("faturas.id"), nullable=False, unique=True),
    Column("conta_id", ForeignKey("contas.id"), nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    Column("valor", money, nullable=False),
    Column("data", Date, nullable=False),
    Column("criado_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("valor > 0", name="ck_pagamentos_fatura_valor_positivo"),
)
Index("ix_pagamentos_fatura_usuario", pagamentos_fatura.c.usuario_id)
Index("ix_pagamentos_fatura_conta", pagamentos_fatura.c.conta_id)

vendas = Table(
    "vendas", metadata,
    Column("id", Integer, primary_key=True),
    Column("cliente", String(160), nullable=False),
    Column("tipo", String(80), nullable=False),
    Column("valor_total", money, nullable=False),
    Column("comentario", Text),
    Column("data", Date, nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    CheckConstraint("valor_total > 0", name="ck_vendas_valor_positivo"),
)
Index("ix_vendas_usuario_data", vendas.c.usuario_id, vendas.c.data)

parcelas = Table(
    "parcelas", metadata,
    Column("id", Integer, primary_key=True),
    Column("venda_id", ForeignKey("vendas.id"), nullable=False),
    Column("valor", money, nullable=False),
    Column("status", String(20), nullable=False, server_default="pendente"),
    Column("data", Date, nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    CheckConstraint("valor > 0", name="ck_parcelas_valor_positivo"),
)
Index("ix_parcelas_usuario_status", parcelas.c.usuario_id, parcelas.c.status)
Index("ix_parcelas_venda", parcelas.c.venda_id)

limites = Table(
    "limites", metadata,
    Column("id", Integer, primary_key=True),
    Column("categoria_id", ForeignKey("categorias.id"), nullable=False),
    Column("valor", money, nullable=False),
    Column("mes", String(7), nullable=False),
    Column("usuario_id", ForeignKey("usuarios.id"), nullable=False),
    UniqueConstraint("categoria_id", "mes", "usuario_id", name="uq_limites_categoria_mes_usuario"),
    CheckConstraint("valor > 0", name="ck_limites_valor_positivo"),
)
Index("ix_limites_usuario_mes", limites.c.usuario_id, limites.c.mes)

conexoes_bancarias = Table(
    "conexoes_bancarias", metadata,
    Column("id", Integer, primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
    Column("provider", String(30), nullable=False),
    Column("external_item_id", String(80), nullable=False),
    Column("client_user_ref", String(120), nullable=False),
    Column("external_connector_id", Integer),
    Column("instituicao_nome", String(160), nullable=False),
    Column("status", String(30), nullable=False),
    Column("ambiente", String(20), nullable=False, server_default="sandbox"),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("atualizada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("ultima_sincronizacao_em", DateTime(timezone=True)),
    Column("desconectada_em", DateTime(timezone=True)),
    UniqueConstraint("provider", "external_item_id", name="uq_conexoes_provider_item"),
    CheckConstraint("ambiente IN ('sandbox', 'production')", name="ck_conexoes_ambiente"),
)
Index("ix_conexoes_usuario_status", conexoes_bancarias.c.usuario_id, conexoes_bancarias.c.status)

contas_bancarias_externas = Table(
    "contas_bancarias_externas", metadata,
    Column("id", Integer, primary_key=True),
    Column("conexao_id", ForeignKey("conexoes_bancarias.id", ondelete="CASCADE"), nullable=False),
    Column("external_account_id", String(80), nullable=False),
    Column("conta_nivra_id", ForeignKey("contas.id", ondelete="SET NULL")),
    Column("nome", String(160), nullable=False),
    Column("tipo", String(40), nullable=False),
    Column("subtipo", String(60)),
    Column("moeda", String(3), nullable=False, server_default="BRL"),
    Column("saldo", money),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("atualizada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("conexao_id", "external_account_id", name="uq_contas_externas_conexao_conta"),
    UniqueConstraint("conta_nivra_id", name="uq_contas_externas_conta_nivra"),
)
Index("ix_contas_externas_conexao", contas_bancarias_externas.c.conexao_id)
Index("ix_contas_externas_conta_nivra", contas_bancarias_externas.c.conta_nivra_id)

transacoes_bancarias = Table(
    "transacoes_bancarias", metadata,
    Column("id", Integer, primary_key=True),
    Column("conta_bancaria_externa_id", ForeignKey("contas_bancarias_externas.id", ondelete="CASCADE"), nullable=False),
    Column("external_transaction_id", String(80), nullable=False),
    Column("descricao", Text, nullable=False),
    Column("valor", money, nullable=False),
    Column("data", Date, nullable=False),
    Column("direcao", String(20), nullable=False),
    Column("status_conciliacao", String(30), nullable=False, server_default="pendente"),
    Column("transacao_nivra_id", ForeignKey("transacoes.id", ondelete="SET NULL")),
    Column("metadata_provider", JSON().with_variant(JSONB, "postgresql")),
    Column("criada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("atualizada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint(
        "conta_bancaria_externa_id",
        "external_transaction_id",
        name="uq_transacoes_bancarias_conta_transacao",
    ),
    UniqueConstraint(
        "transacao_nivra_id",
        name="uq_transacoes_bancarias_transacao_nivra",
    ),
    CheckConstraint("direcao IN ('entrada', 'saida')", name="ck_transacoes_bancarias_direcao"),
    CheckConstraint(
        "status_conciliacao IN ('pendente', 'possivel_correspondencia', 'conciliada', 'ignorada')",
        name="ck_transacoes_bancarias_conciliacao",
    ),
)
Index("ix_transacoes_bancarias_conta_data", transacoes_bancarias.c.conta_bancaria_externa_id, transacoes_bancarias.c.data)
Index("ix_transacoes_bancarias_transacao_nivra", transacoes_bancarias.c.transacao_nivra_id)

eventos_sincronizacao = Table(
    "eventos_sincronizacao", metadata,
    Column("id", Integer, primary_key=True),
    Column("conexao_id", ForeignKey("conexoes_bancarias.id", ondelete="CASCADE"), nullable=False),
    Column("provider_event_id", String(100)),
    Column("tipo", String(60), nullable=False),
    Column("origem", String(30), nullable=False),
    Column("status", String(30), nullable=False),
    Column("iniciada_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finalizada_em", DateTime(timezone=True)),
    Column("quantidade_processada", Integer, nullable=False, server_default="0"),
    Column("codigo_erro", String(80)),
    Column("mensagem_erro", Text),
    CheckConstraint("quantidade_processada >= 0", name="ck_eventos_sync_quantidade"),
)
Index("ix_eventos_sync_conexao_inicio", eventos_sincronizacao.c.conexao_id, eventos_sincronizacao.c.iniciada_em)

eventos_webhook_open_finance = Table(
    "eventos_webhook_open_finance", metadata,
    Column("id", Integer, primary_key=True),
    Column("provider", String(30), nullable=False, server_default="pluggy"),
    Column("provider_event_id", String(100), nullable=False),
    Column("tipo", String(60), nullable=False),
    Column("external_item_id", String(120)),
    Column("conexao_id", ForeignKey("conexoes_bancarias.id", ondelete="SET NULL")),
    Column("status", String(30), nullable=False, server_default="recebido"),
    Column("tentativas", Integer, nullable=False, server_default="1"),
    Column("payload_hash", String(64), nullable=False),
    Column("quantidade_processada", Integer, nullable=False, server_default="0"),
    Column("codigo_erro", String(80)),
    Column("mensagem_erro", Text),
    Column("recebido_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("ultima_tentativa_em", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("processado_em", DateTime(timezone=True)),
    UniqueConstraint("provider", "provider_event_id", name="uq_eventos_webhook_provider_evento"),
    CheckConstraint(
        "status IN ('recebido', 'processando', 'sucesso', 'ignorado', 'erro')",
        name="ck_eventos_webhook_status",
    ),
    CheckConstraint("tentativas >= 1", name="ck_eventos_webhook_tentativas"),
    CheckConstraint(
        "quantidade_processada >= 0",
        name="ck_eventos_webhook_quantidade",
    ),
)
Index(
    "ix_eventos_webhook_item_recebido",
    eventos_webhook_open_finance.c.external_item_id,
    eventos_webhook_open_finance.c.recebido_em,
)

TABLES_IN_DEPENDENCY_ORDER = [
    usuarios, sessoes, auth_tokens, auth_rate_events, categorias, contas, transacoes, transferencias, cartoes,
    faturas, compras_cartao, pagamentos_fatura, vendas, parcelas, limites, conexoes_bancarias,
    contas_bancarias_externas, transacoes_bancarias, eventos_sincronizacao,
    eventos_webhook_open_finance,
]
