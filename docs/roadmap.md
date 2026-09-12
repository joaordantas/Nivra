# Roadmap — Nivra

> Controle financeiro inteligente, simples e automatizado.

A Nivra busca reduzir ao máximo o tempo necessário para organizar, consultar e entender as finanças pessoais. O roadmap abaixo registra capacidades entregues e a ordem planejada; datas e versões podem mudar conforme as validações técnicas e de uso.

## Fundação

- [x] React e TypeScript
- [x] FastAPI
- [x] Interface responsiva
- [x] Navegação desktop e mobile
- [x] Design system e componentes reutilizáveis
- [x] Tema claro e escuro
- [x] Deploy na Vercel
- [x] Identidade visual Nivra
- [x] Logout desktop e mobile

## Núcleo financeiro

- [x] Contas financeiras e saldo por conta
- [x] Saldo total
- [x] Conta principal e conta mais utilizada
- [x] Receitas e despesas
- [x] Transferências neutras em receitas e despesas
- [x] Categorias
- [x] Histórico, busca e filtros
- [x] Criação, edição e exclusão
- [x] Dashboard financeiro
- [x] Isolamento lógico entre usuários

## Infraestrutura

- [x] PostgreSQL no Neon
- [x] Persistência entre deployments
- [x] SQLAlchemy Core e Psycopg 3
- [x] Alembic e migrations versionadas
- [x] `NUMERIC` para valores financeiros
- [x] Foreign keys, constraints e índices úteis
- [x] Operações atômicas
- [x] Proteção dos testes contra o banco de produção
- [x] Migração segura de SQLite para PostgreSQL
- [x] Deploy FastAPI e React na Vercel

## Cartões e faturas — Alpha

- [x] Cadastro, edição e ativação de cartões
- [x] Limite total, utilizado e disponível
- [x] Datas de fechamento e vencimento
- [x] Compras no cartão
- [x] Ciclos, fatura atual e histórico
- [x] Status de fatura
- [x] Pagamento integral integrado às contas
- [x] Proteção contra pagamento duplicado
- [x] Proteção contra dupla contabilização da despesa
- [ ] Pagamentos parciais
- [ ] Estornos e ajustes avançados

## ✅ PRIORIDADE 1 — HARDENING DE CONTA

- [x] Sessões server-side armazenadas no PostgreSQL
- [x] Cookie HTTP-only
- [x] Cookie Secure em produção
- [x] SameSite adequado
- [x] Endpoint `/api/auth/me`
- [x] Logout com revogação real
- [x] Expiração de sessão
- [x] Dependência `current_user` no FastAPI
- [x] Remoção de `usuario_id` das APIs protegidas
- [x] Remoção da autenticação baseada em `localStorage`
- [x] Proteção CSRF
- [x] Revisão de CORS
- [x] Testes de falsificação de usuário
- [x] Testes multiusuário

Melhorias futuras de conta e segurança:

- [x] Recuperação de senha
- [x] Alteração de senha
- [x] Encerrar as outras sessões ao alterar a senha
- [ ] Histórico de sessões e dispositivos
- [x] Rate limiting persistente de login, cadastro e recuperação
- [x] Verificação de e-mail
- [x] Auditoria de IDOR/BOLA nas APIs privadas atuais

Status: **CONCLUÍDA**

## 🏦 PRIORIDADE 2 — OPEN FINANCE MVP

> Objetivo: tornar a Nivra mais simples de testar e demonstrar com dados bancários fictícios, antes de qualquer conexão com bancos reais.

### Etapa 2A — Provider e Sandbox

- [x] Avaliar requisitos atuais da Pluggy
- [ ] Criar ambiente Sandbox
- [-] Configurar credenciais somente no backend — suporte pronto; valores externos pendentes
- [x] Adicionar variáveis de ambiente
- [x] Criar abstração de provider
- [x] Criar endpoint para Connect Token
- [x] Integrar Pluggy Connect no frontend
- [ ] Conectar instituição Sandbox
- [-] Testar fluxo completo — testes automatizados aprovados; validação real pendente

Regra: nenhum secret da Pluggy pode chegar ao frontend.

### Etapa 2B — Persistência

- [ ] `conexoes_bancarias` com proprietário, provider, item externo, instituição, status e timestamps
- [ ] `contas_bancarias_externas` com vínculo à conexão e à conta Nivra
- [ ] `transacoes_bancarias` com identificador externo, valor, data, tipo e estado de conciliação
- [ ] `eventos_sincronizacao` com início, término, status, erro e quantidade importada

### Etapa 2C — Sincronização

- [ ] Importar instituições, contas, saldos e transações
- [ ] Atualizar dados existentes
- [ ] Sincronização manual
- [ ] Exibir última sincronização e erros de conexão

### Etapa 2D — Idempotência

- [ ] Unique constraints para IDs externos
- [ ] Reprocessamento seguro sem duplicar dados
- [ ] Atualizar registros externos existentes
- [ ] Tratar exclusões externas
- [ ] Testes de idempotência

### Etapa 2E — Webhooks

- [ ] Endpoint seguro e validação de autenticidade do provider
- [ ] Eventos de atualização, erro, criação, atualização e exclusão de transações
- [ ] Retry seguro, idempotência e logs estruturados

### Etapa 2F — UX

- [ ] Botão "Conectar banco"
- [ ] Instituição, status e última sincronização
- [ ] Reconectar, sincronizar agora e desconectar
- [ ] Fluxo responsivo, loading, erro e safe area no mobile

### Etapa 2G — Demo para testers

- [ ] Modo Sandbox demonstrável
- [ ] Banco, contas, saldo e histórico fictícios
- [ ] Estado de erro demonstrável
- [ ] Documentar como testar

### Etapa 2H — Conciliação MVP

- [ ] Identificar correspondência com lançamento manual
- [ ] Evitar duplicação e marcar possível correspondência
- [ ] Mesclar somente após confirmação
- [ ] Manter histórico da decisão

### Gate Open Finance Sandbox

- [ ] Connect funciona
- [ ] Conta, saldo e transações externas importados
- [ ] Re-sync e webhook duplicados não criam dados extras
- [ ] Isolamento entre usuários validado
- [ ] Secrets ausentes do frontend
- [ ] Build e testes passam

## 💳 PRIORIDADE 3 — PARCELAMENTOS E RECORRÊNCIAS

### Parcelamentos

- [ ] Compras parceladas
- [ ] Quantidade, parcela atual e parcelas restantes
- [ ] Distribuição entre faturas
- [ ] Comprometimento do limite
- [ ] Projeção de faturas futuras
- [ ] Edição segura e cancelamento quando possível

### Recorrências

- [ ] Receitas e despesas recorrentes
- [ ] Assinaturas
- [ ] Frequência e próxima cobrança
- [ ] Detecção de padrões recorrentes
- [ ] Cancelamento de recorrência

## 🎯 PRIORIDADE 4 — ORÇAMENTOS E METAS

### Orçamentos

- [ ] Limite por categoria e limite mensal total
- [ ] Acompanhamento, valor restante e percentual utilizado
- [ ] Histórico por mês
- [ ] Alertas em 50%, 75%, 90% e 100%

### Metas

- [ ] Valor alvo, valor acumulado e prazo
- [ ] Progresso e valor necessário por mês
- [ ] Metas concluídas e histórico

## 📊 PRIORIDADE 5 — MOTOR DE INTELIGÊNCIA FINANCEIRA

- [ ] Comparação entre períodos
- [ ] Gastos e receitas por categoria
- [ ] Maiores despesas
- [ ] Tendência de gastos e economia
- [ ] Gastos fora do padrão e recorrências
- [ ] Projeção do mês
- [ ] Comprometimento dos cartões
- [ ] Situação de orçamentos e metas
- [ ] Área “Sua atenção” baseada em regras determinísticas

## ✦ PRIORIDADE 6 — LUMI

Lumi será a assistente financeira inteligente da Nivra. A identidade está definida, mas a IA ainda não foi implementada.

- [ ] Consultas financeiras em linguagem natural
- [ ] Criação e edição de transações com confirmação
- [ ] Ações sobre categorias, orçamentos e metas
- [ ] Consultas de contas, cartões e faturas
- [ ] Tool calling para os services existentes
- [ ] Contexto financeiro estruturado e memória de preferências
- [ ] Garantia de que a IA nunca acessa SQL diretamente

## 🔔 PRIORIDADE 7 — NOTIFICAÇÕES INTERNAS

- [ ] `NotificationService` e eventos financeiros
- [ ] Centro de notificações e sino no frontend
- [ ] Estado lida/não lida e preferências
- [ ] Alertas de orçamento e fatura
- [ ] Gastos incomuns e progresso de metas
- [ ] Resumos semanal e mensal

## 💬 PRIORIDADE 8 — WHATSAPP

- [ ] Integração oficial
- [ ] Vinculação, consentimento e preferências
- [ ] Alertas financeiros e de orçamento
- [ ] Alertas de fatura
- [ ] Resumos semanal e mensal

## 🛡️ PRIORIDADE 9 — POLIMENTO E PRODUÇÃO

- [ ] Paginação e filtros server-side
- [ ] Cache quando necessário
- [ ] Error boundaries
- [ ] Monitoramento e logs estruturados
- [x] Rate limiting básico de autenticação
- [ ] Rate limiting geral da API
- [ ] Acessibilidade e performance mobile
- [ ] Auditoria de segurança, backup e recuperação
- [ ] Política de privacidade, termos de uso e LGPD
- [ ] Screenshots oficiais, onboarding e testes públicos

## 🚀 PRIORIDADE 10 — NIVRA PRO

- [ ] Perfil profissional
- [ ] Clientes, vendas e serviços
- [ ] Parcelas a receber e cobranças
- [ ] Produtos, estoque e custos
- [ ] Margens, lucro e dashboard comercial
- [ ] Lumi Pro aplicada ao negócio

## Direção de versionamento

| Linha | Objetivo aproximado |
| --- | --- |
| `v0.1.x-alpha` | Core financeiro, cartões, PostgreSQL e deploy |
| `v0.2.x-alpha` | Autenticação segura, sessões e segurança multiusuário |
| `v0.3.x-alpha` | Open Finance Sandbox, sincronização e conciliação inicial |
| `v0.4.x-alpha` | Parcelamentos, recorrências, orçamentos e metas |
| `v0.5.x-beta` | Inteligência financeira e “Sua atenção” |
| `v0.6.x-beta` | Lumi, consultas e ações |
| `v0.7.x-beta` | Notificações e WhatsApp |
| `v0.8.x` / `v0.9.x` | Preparação para produção |
| `v1.0.0` | Primeira versão pública considerada estável |

## Próxima tarefa recomendada

**Criar ambiente Sandbox da Pluggy e cadastrar as credenciais privadas na Vercel.**

É o primeiro item pendente da prioridade atual. A Nivra não avança automaticamente para ele sem uma nova solicitação.
