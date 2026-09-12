from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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

TABLES_IN_DEPENDENCY_ORDER = [
    usuarios, sessoes, auth_tokens, auth_rate_events, categorias, contas, transacoes, transferencias, cartoes,
    faturas, compras_cartao, pagamentos_fatura, vendas, parcelas, limites,
]
