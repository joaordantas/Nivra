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
- [x] Criar ambiente Sandbox
- [x] Configurar credenciais somente no backend
- [x] Adicionar variáveis de ambiente
- [x] Criar abstração de provider
- [x] Criar endpoint para Connect Token
- [x] Integrar Pluggy Connect no frontend
- [x] Conectar instituição Sandbox
- [x] Testar fluxo completo em produção com o Sandbox PF

Regra: nenhum secret da Pluggy pode chegar ao frontend.

### Etapa 2B — Persistência

- [x] `conexoes_bancarias` com proprietário, provider, item externo, instituição, status e timestamps
- [x] `contas_bancarias_externas` com vínculo à conexão e à conta Nivra
- [x] `transacoes_bancarias` com identificador externo, valor, data, tipo e estado de conciliação
- [x] `eventos_sincronizacao` com início, término, status, erro e quantidade importada

Status: **CONCLUÍDA E VALIDADA EM PRODUÇÃO NO SANDBOX**

### Etapa 2B.5 — Categorias padrão

- [x] Chaves internas estáveis por categoria padrão
- [x] Categorias iniciais para usuários existentes e novos usuários
- [x] Categorias personalizadas preservadas
- [x] Proteção contra exclusão de categorias padrão
- [x] Mapper central com fallback `other` para providers futuros

Status: **CONCLUÍDA**

### Etapa 2C — Sincronização

- [x] Importar instituições, contas, saldos e transações
- [x] Atualizar dados existentes
- [x] Sincronização manual
- [x] Exibir última sincronização e erros de conexão

Status: **CONCLUÍDA E VALIDADA EM PRODUÇÃO NO SANDBOX**

### Etapa 2D — Idempotência

- [x] Unique constraints para IDs externos
- [x] Reprocessamento seguro sem duplicar dados
- [x] Atualizar registros externos existentes
- [x] Tratar exclusões externas
- [x] Testes de idempotência

Status: **CONCLUÍDA E VALIDADA; RE-SYNC VALIDADO EM PRODUÇÃO NO SANDBOX**

### Etapa 2D.5 — Integração Open Finance com o núcleo

> Tornar os dados sincronizados visíveis e úteis no núcleo financeiro antes de automatizar sua atualização por webhooks.

#### Vínculo de contas

- [x] Vincular conta externa a uma conta Nivra existente por `conta_nivra_id`
- [x] Criar uma conta Nivra a partir de uma conta externa
- [x] Exibir e alterar o vínculo com segurança
- [x] Impedir vínculos entre usuários diferentes
- [x] Identificar a origem bancária da conta sem duplicar a relação existente

#### Saldo bancário

- [x] Usar o saldo informado pelo provider como saldo atual da conta vinculada
- [x] Exibir origem e horário da última sincronização do saldo
- [x] Manter o cálculo manual para contas sem vínculo Open Finance
- [x] Incluir contas vinculadas no saldo consolidado sem dupla contagem

#### Histórico unificado

- [x] Unir `transacoes` e `transacoes_bancarias` na camada de consulta
- [x] Não copiar cegamente transações externas para `transacoes`
- [x] Exibir origem `Manual` ou `Banco`
- [x] Preservar busca, filtros, ordenação e isolamento por usuário
- [x] Resolver a categoria externa pela chave estável da categoria padrão do usuário
- [x] Usar fallback `other` para categorias externas desconhecidas

#### Conciliação básica

- [x] Detectar candidatos simples por conta, direção, valor e proximidade de data
- [x] Marcar possível correspondência entre lançamento manual e bancário
- [x] Evitar dupla contagem no histórico e no resumo financeiro
- [x] Permitir confirmar ou rejeitar a correspondência
- [x] Preservar os dois registros de origem para auditoria

#### Dashboard

- [x] Considerar saldos bancários das contas vinculadas
- [x] Considerar receitas e despesas externas vinculadas
- [x] Aplicar a conciliação antes de calcular totais
- [x] Exibir atualização e origem dos dados bancários
- [x] Validar que transferências internas não alteram receitas ou despesas

#### Gate da Etapa 2D.5

- [x] Conta externa pode criar ou vincular uma conta Nivra
- [x] Saldo bancário aparece uma única vez no saldo consolidado
- [x] Transações bancárias aparecem no histórico principal
- [x] Categorias padrão são resolvidas pela chave interna
- [x] Lançamentos conciliados não são contados duas vezes
- [x] Dashboard combina dados manuais e bancários corretamente
- [x] Usuário A não acessa vínculos ou dados do usuário B
- [x] Testes Python e build React/TypeScript passam

Status: **CONCLUÍDA E VALIDADA EM PRODUÇÃO NO SANDBOX**

### Etapa 2E — Webhooks

- [x] Endpoint seguro e validação de autenticidade do provider
- [x] Eventos de atualização, erro, criação, atualização e exclusão de transações
- [x] Retry seguro, idempotência e logs estruturados

Evidências reais em produção: entregas `item/updated`, `transactions/created` e `transactions/updated` receberam HTTP 200. O evento informativo `item/login_succeeded` foi ignorado com segurança. A inbox não possui IDs duplicados e todos os eventos reais observados tiveram uma tentativa. Ainda falta comprovar externamente a repetição do mesmo `eventId` sem duplicação.

Status: **IMPLEMENTADA E PUBLICADA; RETRY EXTERNO DO MESMO EVENTO AINDA PENDENTE**

### Etapa 2F — UX

- [x] Botão "Conectar banco"
- [x] Instituição, status compreensível e última sincronização
- [x] Atualizar dados com estado de carregamento, sucesso e erro
- [x] Contas externas, saldos, vínculo e criação de conta Nivra em modal responsivo
- [x] Fluxo responsivo, loading, empty states e safe area no mobile

Reconexão e desconexão não são exibidas: ainda não existe um fluxo backend/provider completo e seguro para essas ações. Elas permanecem pendentes, sem simular uma capacidade inexistente.

Status: **CONCLUÍDA**

### Etapa 2G — Demo para testers

- [x] Modo Sandbox demonstrável
- [x] Banco, contas, saldo e histórico fictícios
- [x] Estado de erro compreensível com nova tentativa disponível
- [x] Guia de teste, checklist e modelo de relato de bug

Status: **IMPLEMENTADA E PUBLICADA; VALIDAÇÃO EXTERNA COM TESTERS PENDENTE**

### Etapa 2H — Conciliação avançada

- [x] Melhorar correspondências com descrição normalizada, janela temporal e regras centralizadas
- [x] Tratar correspondências de múltiplos lançamentos e casos ambíguos
- [x] Oferecer revisão e confirmação segura em lote para alta confiança
- [x] Manter histórico das sugestões, confirmações, rejeições e reaberturas
- [x] Reabrir decisões após alteração econômica relevante ou remoção bancária
- [x] Preservar uma única representação econômica no histórico e no dashboard
- [x] Validar ownership, CSRF, idempotência e confirmação concorrente

Status: **IMPLEMENTADA, PUBLICADA E VALIDADA EM PRODUÇÃO NO SANDBOX**

### Gate final da Prioridade 2 — Open Finance MVP

- [x] Connect, sincronização, vínculo, saldo e histórico funcionam no Sandbox
- [x] Re-sync não duplica dados
- [x] Conciliação avançada passou nos testes automatizados
- [-] Webhook repetido é idempotente nos testes; retry externo do mesmo `eventId` ainda sem evidência
- [x] Experiência de conciliação validada em produção nos temas claro/escuro e em 375, 390, 430 e 1440 px
- [x] Isolamento entre usuários e proteção CSRF validados
- [x] Secrets permanecem fora do frontend e da documentação pública
- [x] Suite Python, migration descartável, Alembic e build passam

Status: **PRIORIDADE 2 TECNICAMENTE CONCLUÍDA; GATE EXTERNO PENDENTE**

Validações externas complementares:

- [-] Replay real do mesmo `eventId` enviado pela Pluggy
- [-] Execução integral do roteiro por testers independentes

### Evidências técnicas do Open Finance Sandbox

- [x] Connect funciona
- [x] Conta, saldo e transações externas importados
- [x] Re-sync não cria dados extras
- [x] Webhook duplicado não cria dados extras nos testes e está protegido por constraint
- [-] Replay real do mesmo `eventId` no Sandbox — evidência externa complementar pendente
- [x] Isolamento entre usuários validado
- [x] Secrets ausentes do frontend
- [x] Build e testes passam

## 💳 PRIORIDADE 3 — PARCELAMENTOS E RECORRÊNCIAS

### P3.1 — Fundação de Parcelamentos

- [x] Entidade própria para representar o parcelamento completo
- [x] Parcelas persistidas como transações financeiras reais
- [x] Relação estável entre plano, número da parcela e transação
- [x] Divisão monetária determinística com soma exata
- [x] Datas mensais com ajuste para o último dia válido
- [x] Criação e exclusão do grupo em transações atômicas
- [x] Isolamento por usuário, foreign keys, checks, unique constraints e índices
- [x] API mínima para criar, listar, consultar e excluir parcelamentos
- [x] Proteção contra edição ou exclusão isolada de uma parcela

Status: **CONCLUÍDA E VALIDADA EM BANCO DESCARTÁVEL**

### P3.2 — UX e integração de parcelamentos

- [x] Criar despesas e receitas parceladas pelo formulário normal de movimentações
- [x] Exibir preview honesto antes da criação e preservar o backend como fonte do cálculo monetário
- [x] Identificar parcelas por metadado visual `X/Y` no histórico
- [x] Listar planos e consultar todas as parcelas do grupo
- [x] Exibir progresso temporal sem tratar data atingida como pagamento
- [x] Editar descrição, categoria e conta de todo o grupo atomicamente
- [x] Excluir explicitamente o grupo completo, sem exclusão isolada
- [x] Manter parcelas futuras no histórico sem afetar saldo e resumo atuais
- [x] Cobrir loading, erro, vazio, sucesso e bloqueio de ações repetidas
- [x] Preservar layout responsivo e temas claro/escuro

#### Gate de UX mobile da P3.2

- [x] Rota dedicada de parcelamentos acessível no desktop e no menu mobile "Mais"
- [x] Atalho central `+` abre o formulário com foco no valor
- [x] Histórico abre sem deslocamento automático para o formulário
- [x] Detalhe e edição usam modal de tela inteira com ação "Voltar" no mobile
- [x] Navegação mobile mantém acesso a Início, Histórico, Contas, criação, finanças, configurações e logout
- [x] Safe areas, rolagem e ausência de overflow validadas em 375, 390, 430, 612 e 1440 px
- [x] Temas claro e escuro preservados

Status: **CONCLUÍDA E VALIDADA; GATE DE UX MOBILE APROVADO**

### Próximos incrementos de parcelamentos

- [ ] Integração com cartões e distribuição entre faturas
- [ ] Comprometimento do limite
- [ ] Projeção de faturas futuras
- [ ] Alterações estruturais seguras de valor, quantidade e data inicial
- [ ] Cancelamento parcial quando houver uma semântica financeira definida

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

- [x] Comparação entre períodos
- [x] Gastos e receitas por categoria
- [x] Maiores despesas
- [x] Tendência de gastos e economia
- [x] Gastos fora do padrão e recorrências detectadas por regras determinísticas
- [x] Projeção do mês
- [x] Comprometimento dos cartões
- [ ] Situação de orçamentos e metas
- [x] Área “Sua atenção” baseada em regras determinísticas

### P5.1 — Insights determinísticos iniciais

- [x] Endpoint autenticado `GET /api/insights`
- [x] Comparação com período anterior equivalente
- [x] Totais de receitas e despesas por categoria
- [x] Compras no cartão incluídas sem contar o pagamento da fatura novamente
- [x] Transferências internas excluídas dos alertas financeiros
- [x] Detecção inicial de gasto incomum baseada em mediana e amostra mínima
- [x] Alertas de resultado negativo, aumento de gastos, concentração por categoria e economia positiva
- [x] Dashboard com múltiplos avisos e falha isolada do restante do resumo
- [x] Isolamento por sessão e testes de propriedade

Status: **PRIMEIRA UNIDADE CONCLUÍDA; MOTOR AINDA EM EVOLUÇÃO**

### P5.2 — Projeção mensal e comprometimento de cartões

- [x] Separação entre realizado, compromissos futuros conhecidos e resultado projetado
- [x] Parcelas e demais movimentações futuras persistidas incluídas somente no futuro conhecido
- [x] Transferências neutras e conciliações representadas uma única vez
- [x] Compras no cartão contabilizadas como despesa econômica sem duplicar o pagamento da fatura
- [x] Limite total, comprometido, disponível e percentual por cartão ativo
- [x] Resumo agregado dos cartões ativos
- [x] Próxima fatura pendente identificada separadamente do ciclo atual
- [x] Alertas de projeção negativa, limite elevado/crítico, concentração e vencimento
- [x] Dashboard responsivo com projeção conservadora e resumo dos cartões
- [x] Contrato ampliado disponível para a ferramenta somente leitura da futura Lumi

Status: **CONCLUÍDA E VALIDADA; MOTOR AINDA EM EVOLUÇÃO**

### P5.3 — Tendências, maiores despesas e contexto da Lumi

- [x] Ranking das cinco maiores despesas do período com participação percentual
- [x] Despesas manuais, bancárias e de cartão analisadas na mesma visão econômica
- [x] Transferências internas e duplicações conciliadas excluídas do ranking
- [x] Série de seis meses com receitas, despesas e economia
- [x] Comparação por mês completo ou pelo mesmo dia, conforme o período em andamento
- [x] Direção de tendência com faixa estável e tratamento de base zerada
- [x] Alerta de crescimento contínuo por três períodos equivalentes
- [x] Dashboard responsivo com evolução recente e maiores gastos
- [x] Contexto financeiro consolidado para a futura Lumi
- [x] Ferramenta somente leitura `get_financial_context`, com identidade da sessão

Status: **CONCLUÍDA E VALIDADA; SEM MODELO DE IA CONECTADO**

### P5.4 — Recorrências determinísticas e gastos fora do padrão

- [x] Normalização conservadora e centralizada de descrições financeiras
- [x] Recorrências detectadas somente com três ou mais ocorrências
- [x] Frequências semanal, quinzenal, mensal, aproximadamente mensal e anual
- [x] Tolerâncias temporais e de valor centralizadas e testáveis
- [x] Confiança média/alta derivada de regularidade, amostra e estabilidade de valor
- [x] Próxima ocorrência estimada somente quando todos os intervalos são consistentes
- [x] Mudanças relevantes no valor típico identificadas sem alterar movimentações
- [x] Parcelamentos, transferências e pagamentos de fatura excluídos dos padrões comuns
- [x] Anomalias globais e por categoria com baseline exclusivamente histórica
- [x] Mediana e MAD usados para resistir a outliers e explicar cada detecção
- [x] Contrato tipado ampliado em `GET /api/insights`
- [x] Contexto da futura Lumi com recorrências, próximas cobranças, mudanças e anomalias
- [x] Dashboard responsivo com recorrências e gastos relevantes fora do padrão
- [x] Implementação sem persistência adicional e sem nova migration

Status: **CONCLUÍDA E VALIDADA; ANÁLISE SOMENTE LEITURA E SEM IA GENERATIVA**

## ✦ PRIORIDADE 6 — LUMI

Lumi é a assistente financeira inteligente da Nivra. A orquestração, a
interface e um contexto curto e efêmero estão disponíveis. Consultas permanecem
somente leitura; receita e despesa podem ser executadas após confirmação explícita
somente quando duas flags independentes forem habilitadas. A execução permanece
desligada por padrão e a memória persistente continua pendente.

- [x] Consultas financeiras em linguagem natural com contexto efêmero e somente leitura
- [-] Fundação de propostas para criação de receitas e despesas com confirmação explícita
- [x] Execução controlada de receita e despesa após confirmação explícita, validada localmente
- [ ] Edição de transações com confirmação
- [ ] Ações sobre categorias, orçamentos e metas
- [x] Consultas de contas, cartões e faturas pelo contexto financeiro consolidado
- [x] Tool calling somente leitura para os services existentes
- [x] Contexto financeiro estruturado
- [ ] Memória persistente de preferências e histórico de conversa
- [x] Garantia arquitetural e testes de que a IA não acessa SQL ou repositories diretamente

### Preparação técnica da Lumi

- [x] Catálogo inicial de ferramentas permitido por lista explícita
- [x] Primeira ferramenta somente leitura para consultar insights financeiros
- [x] Identidade injetada a partir da sessão, sem aceitar `usuario_id` dos argumentos
- [x] Execução pela camada de service, sem acesso direto da futura IA a repository ou SQL
- [x] Contexto consolidado com posição financeira, tendência, maiores gastos, projeção, cartões e alertas
- [x] Contexto determinístico com recorrências, próximas cobranças, mudanças de valor e anomalias explicáveis
- [x] Orquestração com OpenAI Responses API e tool calling real
- [x] Provider isolado por protocolo e substituível por fake nos testes
- [x] Endpoint autenticado `POST /api/lumi/message`, com sessão, CSRF e schema fechado
- [x] Allowlist estrita expondo apenas `get_financial_context` ao modelo
- [x] Perguntas não triviais exigem tool antes de qualquer resposta financeira
- [x] Loop sequencial com validação de argumentos e limite rígido de quatro tools por mensagem
- [x] Instruções de sistema versionadas e proteção contra prompt injection nos dados
- [x] Execução com `store=false` e contexto efêmero limitado, sem persistência de conversa
- [x] Timeout, limite de saída, rate limit próprio e métricas sanitizadas
- [x] Ausência do provider isolada do restante da aplicação
- [x] Interface de conversa responsiva na rota `/lumi`
- [x] Seleção explícita de provider por `LUMI_PROVIDER`, sem fallback automático
- [x] Adaptadores independentes para OpenAI Responses API e Groq Chat Completions
- [x] Mesmo catálogo local e somente leitura de tools para ambos os providers

### P6.3a — Provider Groq alternativo

- [x] `GroqProvider` implementa o contrato `LLMProvider`
- [x] Factory central escolhe exclusivamente `openai` ou `groq`
- [x] Modelo Groq configurável, com padrão `openai/gpt-oss-20b`
- [x] Conversão isolada entre o contrato interno e local function calling da Groq
- [x] Rate limit e falhas de autenticação da Groq sanitizados no backend
- [x] OpenAIProvider preservado sem fallback automático entre providers
- [x] Testes offline de factory, tool calling, continuação, timeout, rate limit e autenticação
- [x] Suíte completa, build, compilação Python e Alembic validados sem migration nova
- [x] Smoke real mínimo da Groq

Status: **IMPLEMENTADA E VALIDADA; GATE EXTERNO MÍNIMO APROVADO**

Gate externo mínimo executado em 22 de setembro de 2026 com
`LUMI_PROVIDER=groq`, modelo `openai/gpt-oss-20b`, banco descartável e sessão
autenticada. As cinco mensagens passaram com HTTP 200; `get_financial_context`
foi a única tool usada nas consultas financeiras e nenhuma escrita ocorreu.
O gate não habilita OpenAI Production nem altera o escopo somente leitura.

### P6.1 — Orquestração segura em modo somente leitura

Status: **CONCLUÍDA E VALIDADA NO BACKEND; SEM INTERFACE, MEMÓRIA OU AÇÕES**

### P6.2 — Interface de conversa em modo somente leitura

- [x] Rota protegida `/lumi`
- [x] Acesso pela sidebar desktop e menu mobile “Mais”
- [x] Estado inicial, sugestões de perguntas, mensagens e processamento
- [x] Composer com limite de 2.000 caracteres, Enter e Shift+Enter
- [x] Bloqueio imediato de envio duplicado
- [x] Erros sanitizados para sessão, CSRF, limite, provider, timeout e conexão
- [x] Retry manual para falhas temporárias, sem retentativa automática
- [x] Tratamento do `Retry-After` sem substituir a autoridade do backend
- [x] Renderização como texto seguro, sem HTML arbitrário ou Markdown executável
- [x] Histórico somente em memória React e limpeza no reload
- [x] Cancelamento da request no desmonte com `AbortController`
- [x] Identidade visual, temas e acessibilidade básica preservados
- [x] Layout validado em 375, 390, 430, 612 e 1440 px
- [x] Request restrita ao contrato `{ message, history }`, sem parâmetros de identidade, modelo ou tools
- [x] Nenhuma migration ou persistência de conversa
- [x] Suíte Python completa com 167 testes e build React/TypeScript aprovados
- [x] Alembic no head `f7b3c1d8e920` e sem novas operações
- [x] Gate local de regressão pré-commit aprovado
- [ ] Smoke real com OpenAI no ambiente externo

Status: **APROVADA LOCALMENTE; INTEGRAÇÃO EXTERNA DA LUMI PENDENTE DE SMOKE REAL**

### P6.3 — Contexto efêmero e multi-turn seguro

- [x] Até três turnos completos anteriores enviados somente durante a página aberta
- [x] Limite de seis mensagens e 12.000 caracteres de contexto no frontend e backend
- [x] Papéis restritos a `user` e `assistant`, com alternância e turnos completos validados
- [x] Histórico tratado como conteúdo não confiável pelas instruções do backend
- [x] Pergunta financeira atual continua exigindo nova execução da tool autorizada
- [x] Falhas sem resposta não entram no contexto enviado ao provider
- [x] Reload e saída da rota descartam todo o contexto
- [x] Nenhuma tabela, migration, `localStorage`, cookie ou memória persistente adicionada
- [x] Testes offline de limites, ordenação, ownership e continuidade aprovados
- [x] Suíte completa com 169 testes, build e gate Alembic descartável aprovados
- [ ] Smoke multi-turn real com OpenAI e medição de latência/custo

Status: **APROVADA LOCALMENTE; GATE EXTERNO MULTI-TURN PENDENTE**

### P6.4 — Fundação de ações com confirmação explícita

- [x] Tipos fechados `create_expense` e `create_income`, sem tool de escrita para o modelo
- [x] Proposta estruturada e validada pelo backend, com valor decimal, conta, categoria, descrição e data explícitos
- [x] Campos faltantes e avisos devolvidos sem inventar valores, data, conta ou categoria
- [x] Conta e categoria resolvidas exclusivamente entre entidades do usuário autenticado
- [x] Persistência curta server-side em `lumi_action_confirmations`, sem prompt, histórico ou reasoning
- [x] `confirmation_id` opaco, aleatório e armazenado somente como hash
- [x] Estados `pending`, `confirmed`, `cancelled` e `expired`, com expiração padrão de 10 minutos
- [x] Endpoints autenticados para confirmação e cancelamento, protegidos por CSRF e ownership
- [x] Transição atômica por condição SQL, protegendo replay e confirmações concorrentes
- [x] Rate limit específico para propostas e operações de confirmação
- [x] Feature flag `LUMI_ACTION_PROPOSALS_ENABLED=false` por padrão
- [x] Card de proposta responsivo com revisão explícita, confirmação e cancelamento
- [x] Confirmação sem execução: nenhuma receita, despesa ou outra mutação financeira é criada nesta etapa
- [x] Migration `e9a2d6c3b4f1` e testes de proposta, ownership, CSRF, expiração, replay e concorrência

Status: **CONCLUÍDA E VALIDADA LOCALMENTE; EXECUÇÃO FINANCEIRA PERMANECE DESABILITADA**

### P6.5 — Execução controlada de receita e despesa

- [x] Apenas `create_expense` e `create_income`, sem tool de escrita para o modelo
- [x] `LUMI_ACTION_EXECUTION_ENABLED=false` independente da flag de propostas
- [x] Confirmação HTTP com sessão e CSRF como única autorização
- [x] Payload persistido revalidado no instante da execução, inclusive conta/categoria do usuário
- [x] Valor `Decimal`, data e descrição preservados do card
- [x] Criação pela camada de serviço financeiro na mesma transação da confirmação
- [x] Estado `executed`, vínculo com transação e retry idempotente
- [x] `execution_eligible=false` para propostas anteriores ao rollout e confirmações P6.4 não executáveis
- [x] Testes locais de replay, concorrência, rollback, ownership, expiração e cancelamento
- [x] Card mostra sucesso apenas após resposta do commit e oferece histórico normal
- [x] Gate de execução em PostgreSQL descartável: migrations, atomicidade, replay, concorrência, isolamento e núcleo financeiro
- [x] Rollout de schema no Neon principal concluído em `b5c7d9e1f203`, com execução desligada, migrations expand-only e `alembic check` limpo
- [x] P6.5A: Gate Production aprovado com ressalvas. O código validado no Preview foi publicado, o Neon principal foi migrado sem alterar saldos ou criar transações, e `LUMI_PUBLIC_ENABLED=false`, `LUMI_ACTION_PROPOSALS_ENABLED=false` e `LUMI_ACTION_EXECUTION_ENABLED=false` permaneceram explícitas em Production. Auth, núcleo financeiro, Open Finance, cartões, parcelamentos, responsividade e temas passaram pelo smoke direcionado; mutações completas permaneceram cobertas pelo Preview e pelos 208 testes para evitar dados desnecessários em Production.
- [x] Gate Preview P6.5A: auth, contas, transferências, transações, dashboard, categorias, cartões, parcelamentos, pagamento integral de fatura, proteção contra pagamento duplicado, Pluggy Sandbox, sincronização repetida, vínculo com o núcleo, histórico unificado, Lumi bloqueada e badge Alpha foram validados com dados fictícios. O Gate Preview foi aprovado sem merge, migration ou deploy em Production. A conciliação Open Finance não foi exercitada por falta de um par compatível; o webhook Preview também não foi redirecionado nem testado nesta execução.
- [ ] Observação em produção e habilitação explícita da execução após aprovação humana

Status: **P6.5A PUBLICADA E APROVADA COM RESSALVAS; PRODUÇÃO SEM LUMI PÚBLICA OU EXECUÇÃO FINANCEIRA**

O gate passou em `nivra_p65_gate`, projeto Neon descartável com endpoint
distinto do principal: `upgrade → check → downgrade → upgrade → check`, duas
confirmações P6.4 inelegíveis, execução de despesa/receita exatas, rollback,
replay, concorrência HTTP de 2 e 5 requisições sem duplicação, ownership, CSRF,
e histórico/saldo/insights. A leitura final mostrou sete transações fictícias,
sete vínculos de autorização completos e nenhuma transação órfã. O teste de
proposta estruturada *gerada pela Groq* não foi feito: o parser determinístico
legítimo captura intenções de escrita antes do provider. Zero chamadas externas
foram feitas neste gate. Nenhum rollout ocorreu no Neon principal ou Vercel.

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

**Concluir a Fase A do rollout P6.5 após o checkpoint Git e autorização de
publicação: aplicar o schema no Neon principal com execução desligada e comparar
a aplicação publicada com a baseline registrada.**

A execução de receita e despesa está desligada por padrão. O gate em PostgreSQL
descartável passou com ressalvas; aplicação de schema e habilitação em produção
exigem decisões separadas. A próxima ação financeira funcional ainda pendente é a edição
de transações com confirmação; ela não faz parte da P6.5.
