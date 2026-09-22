# Changelog

Todas as alterações importantes da Nivra serão documentadas neste arquivo. O formato segue os princípios do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/) durante sua evolução pré-1.0.

## [Unreleased]

### Added

- trava pública server-side `LUMI_PUBLIC_ENABLED=false` por padrão; a página
  Lumi permanece “Em breve” e os endpoints de conversa/ação não acionam o
  provider enquanto a liberação pública não for autorizada;
- preparação do rollout P6.5A: revisão da cadeia Alembic, baseline da versão
  pública e snapshot de recuperação no Neon principal; schema de produção ainda
  não alterado;
- indicador Alpha acessível no shell desktop/mobile e aviso de estágio da Lumi,
  preservando o aviso específico do Open Finance Sandbox.

- P6.5: execução determinística de uma receita ou despesa após confirmação HTTP
  explícita, protegida por sessão, CSRF, ownership e revalidação do payload;
- flag independente `LUMI_ACTION_EXECUTION_ENABLED=false` por padrão, com
  inelegibilidade das propostas anteriores ao rollout;
- migration `b5c7d9e1f203` para estado `executed`, vínculo da transação e
  idempotência, com criação e registro em um único commit;
- revisão do card da Lumi para mostrar o resultado da execução e acesso ao
  histórico financeiro após sucesso.

- fundação de propostas de ação da Lumi para receitas e despesas, com schemas
  fechados, valores decimais e resolução de conta/categoria restrita ao usuário
  autenticado;
- confirmação server-side temporária com token opaco armazenado somente como
  hash, expiração, cancelamento idempotente e transição atômica contra replay;
- endpoints de confirmação e cancelamento protegidos por sessão, CSRF,
  ownership e rate limit próprio; na P6.4 não havia mutação financeira;
- card responsivo de proposta da Lumi e feature flag
  `LUMI_ACTION_PROPOSALS_ENABLED=false` por padrão;
- migration `e9a2d6c3b4f1` para `lumi_action_confirmations`, sem prompts,
  histórico ou reasoning persistidos.

- provider Groq alternativo para a Lumi, selecionado explicitamente por
  `LUMI_PROVIDER` e sem fallback automático para OpenAI;
- factory central de providers e adaptador para local function calling da Groq,
  mantendo somente `get_financial_context` como tool permitida;
- tratamento sanitizado de rate limit e autenticação do provider, com métricas
  de provider adicionadas aos logs técnicos da Lumi;
- contexto conversacional efêmero da Lumi com até três turnos completos,
  limitado a seis mensagens e 12.000 caracteres, descartado ao recarregar;
- validação no backend de papéis, alternância, tamanho e completude do histórico,
  mantendo a identidade da sessão e uma nova consulta às tools para perguntas
  financeiras atuais;
- interface de conversa responsiva da Lumi na rota protegida `/lumi`, acessível
  pela sidebar desktop e pelo menu mobile “Mais”;
- estado inicial com sugestões, histórico visual somente em memória, composer
  acessível, processamento, retry manual e indicação de modo somente leitura;
- tratamento amigável de sessão, CSRF, rate limit com `Retry-After`, provider,
  timeout e conexão, sem expor detalhes internos;
- renderização das respostas como texto seguro, cancelamento no desmonte e
  bloqueio síncrono de envios duplicados;
- endpoint autenticado `POST /api/lumi/message` para a primeira orquestração
  stateless e somente leitura da Lumi;
- abstração `LLMProvider` e implementação OpenAI Responses API carregada sob
  demanda, com `store=false`, timeout e limite de saída configuráveis;
- tool calling sequencial e limitado, expondo somente
  `get_financial_context` por JSON Schema estrito e allowlist do backend;
- exigência determinística de tool para mensagens não triviais, impedindo que
  perguntas financeiras sejam respondidas sem consultar a fonte autorizada;
- instruções de sistema versionadas, proteção contra prompt injection,
  `safety_identifier` opaco e serialização controlada de valores financeiros;
- rate limit persistente próprio da Lumi e métricas sanitizadas de tokens,
  duração, modelo, sucesso e número de tools;
- testes offline com provider falso para autenticação, CSRF, isolamento,
  read-only, erros do provider, loops, argumentos inválidos e prompt injection;
- detecção determinística de despesas recorrentes com amostra mínima, frequências de calendário, confiança e previsão conservadora da próxima ocorrência;
- normalização centralizada de descrições financeiras, tolerância controlada de valores e detecção de aumento relevante em recorrências;
- análise robusta de gastos fora do padrão com baseline histórica global e por categoria, mediana, MAD e explicação do critério;
- contexto da futura Lumi ampliado com recorrências, próximas cobranças estimadas, mudanças de valor e anomalias, sempre identificadas como inferências determinísticas;
- blocos responsivos de recorrências e gastos fora do padrão no Dashboard, com loading, vazio e falha isolada;
- testes para frequências, calendário, valores, parcelamentos, cartões, Open Finance, movimentos neutros, anomalias e isolamento multiusuário;
- tendência financeira determinística de seis meses, comparando meses completos ou períodos equivalentes até o mesmo dia;
- ranking das maiores despesas com participação no total, incluindo movimentações manuais, bancárias e compras no cartão sem duplicação econômica;
- alerta de crescimento contínuo dos gastos baseado em três períodos mensais equivalentes;
- contexto financeiro consolidado e ferramenta somente leitura `get_financial_context` para preparar a futura Lumi sem acesso a SQL;
- blocos responsivos de tendência recente e maiores gastos no Dashboard.

- projeção mensal conservadora que separa valores realizados, compromissos futuros conhecidos e resultado projetado;
- comprometimento individual e agregado dos cartões ativos, com limite disponível e próxima fatura pendente;
- alertas determinísticos para projeção negativa, limite elevado ou crítico, concentração entre cartões e fatura próxima do vencimento;
- cartões compactos de projeção e comprometimento no Dashboard, com estados responsivos, vazio, carregamento e falha isolada;
- testes de projeção, datas de fechamento, parcelas futuras, cartões, faturas, conciliação, Open Finance e isolamento multiusuário;
- endpoint autenticado de insights com comparação entre períodos, categorias de receita/despesa e gastos incomuns;
- área “Sua atenção” alimentada por regras determinísticas para resultado negativo, aumento de gastos, concentração por categoria e economia positiva;
- catálogo inicial de ferramentas da Lumi com execução restrita a services e identidade obtida pela sessão;
- testes de cálculo, cartões, período efetivo, autenticação, isolamento e bloqueio de ferramentas não permitidas da Lumi;
- acesso à saída da conta pelo menu mobile “Mais”, reutilizando o mesmo contexto de autenticação do desktop;
- guia para a renomeação manual e segura do repositório GitHub e do projeto Vercel;
- sessões server-side persistidas no PostgreSQL com expiração;
- cookie de sessão HTTP-only, SameSite Lax e Secure em produção;
- endpoint `/api/auth/me` para restaurar a sessão;
- proteção CSRF em login, cadastro, logout e operações financeiras de escrita;
- migration Alembic para a tabela `sessoes`;
- testes de revogação, expiração, CORS, CSRF, falsificação de usuário e isolamento multiusuário.
- verificação de e-mail e reenvio com tokens de uso único;
- recuperação e alteração de senha;
- telas de recuperação, redefinição e segurança da conta;
- migration para tokens de conta, estado de verificação e eventos de limite;
- rate limiting persistente nas operações sensíveis de autenticação;
- testes de expiração, reutilização de token, enumeração de conta e IDOR/BOLA.
- persistência das conexões Pluggy Sandbox com validação server-side do Item;
- tabelas preparatórias para contas externas, transações bancárias e eventos de sincronização;
- listagem isolada das conexões bancárias e restauração do estado após novo login;
- proteção idempotente contra callbacks repetidos e reivindicação de Item por outro usuário.
- ativação da persistência Open Finance Sandbox no Neon e publicação do fluxo na Vercel.
- categorias padrão por usuário com chaves internas estáveis e proteção contra exclusão;
- sincronização manual de contas, saldos e transações da Pluggy com paginação por cursor;
- atualização idempotente de registros externos e remoção de dados que deixaram de existir no snapshot completo;
- histórico de sucesso e falha das sincronizações, com última execução exibida na página de Contas.
- ativação das Etapas 2C/2D em produção, com 2 contas e 41 transações Sandbox importadas e re-sync validado sem duplicação.
- vínculo de contas bancárias externas com contas Nivra existentes;
- criação atômica de uma conta Nivra a partir de uma conta bancária sincronizada;
- saldo bancário como fonte do saldo atual para contas vinculadas, com origem e horário da sincronização;
- proteção de unicidade para impedir que duas contas externas usem a mesma conta Nivra.
- histórico unificado de lançamentos manuais e bancários sem copiar os registros externos;
- categorização bancária por chave interna estável, com fallback seguro para `Outros`;
- conciliação básica de possíveis duplicações, com confirmação, rejeição e preservação dos registros de origem;
- proteção de unicidade para impedir que um lançamento manual seja conciliado com mais de uma transação bancária.
- endpoint autenticado para webhooks Pluggy e caixa de entrada persistente por `eventId`;
- processamento de `item/updated`, `item/error`, `item/deleted` e eventos de criação, atualização e exclusão de transações;
- retentativa segura de eventos com falha, reivindicação atômica contra concorrência, deduplicação e logs estruturados sem payload financeiro;
- utilitário para cadastrar ou atualizar o webhook com header secreto na API da Pluggy.
- experiência Open Finance na página de Contas, com estado vazio, conexões, status legíveis, última atualização e feedback de sincronização;
- modal responsivo para vincular uma conta externa a uma conta Nivra existente ou criar uma nova conta sincronizada;
- indicação discreta de banco conectado e saldo atualizado pelo banco nas contas Nivra;
- apresentação somente para consulta de cartões externos enquanto a integração com cartões não estiver disponível.
- guia curto de demonstração Open Finance dentro de Contas, com etapas de conexão, sincronização, vínculo e histórico;
- credenciais fictícias oficiais do Pluggy Bank exibidas de forma expansível, com aviso para nunca usar dados bancários reais;
- guia público de teste Sandbox, checklist de regressão e modelo seguro de relato de bug;
- orientações de primeiro uso sem dados no Dashboard, Contas e Transações.
- motor determinístico de conciliação com janela de dois dias, normalização de descrições e níveis de confiança;
- histórico persistente de sugestões, confirmações, rejeições e reaberturas de correspondências;
- revisão de casos ambíguos e confirmação em lote restrita a correspondências únicas de alta confiança;
- filtros de origem para movimentações manuais, bancárias e conciliadas;
- arquivamento de transações bancárias removidas sem excluir o lançamento manual correspondente.
- publicação da conciliação avançada no Sandbox, com smoke test autenticado e validação responsiva em produção.
- fundação de parcelamentos com entidade própria, parcelas financeiras vinculadas e API autenticada para criação, consulta, listagem e exclusão do grupo;
- divisão monetária exata em centavos e calendário mensal previsível para dias inexistentes no mês de destino;
- migration Alembic com integridade por usuário, numeração única das parcelas e compatibilidade com transações já existentes;
- testes de atomicidade, ownership, datas, valores, API e regressão das transações normais.
- criação de despesas e receitas parceladas dentro do formulário normal de movimentações;
- painel compacto de parcelamentos, detalhe de todas as parcelas e identificação `X/Y` no histórico;
- edição atômica de descrição, categoria e conta do grupo e exclusão integral com confirmação explícita;
- progresso baseado em datas, claramente separado de qualquer estado de pagamento.

### Changed

- a árvore local passou por gate de regressão antes do próximo commit, com
  suíte Python completa, build React/TypeScript, compilação Python e validação
  Alembic em banco descartável aprovados;
- a navegação da Lumi passou de `/assistant` para `/lumi`, mantendo redirect de
  compatibilidade para a rota anterior;
- o client HTTP agora preserva status e `Retry-After` em erros tipados para que
  a interface trate falhas sem interpretar mensagens técnicas;
- o catálogo da Lumi passou a separar tools internas das tools efetivamente
  expostas ao modelo; a P6.1 disponibiliza somente `get_financial_context`;
- o teste de parcelas futuras usa uma margem temporal estável para não depender
  da virada de data entre o fuso local e `CURRENT_DATE` do banco;
- `GET /api/insights` preserva o contrato anterior e acrescenta recorrências tipadas e anomalias explicáveis;
- a detecção de anomalias usa somente movimentações anteriores à despesa analisada, evitando comparar o gasto consigo mesmo;
- consultas bancárias do histórico unificado agora recebem a janela solicitada, evitando carregar dados externos fora do período;
- o motor de insights passou a consultar o histórico da tendência em uma única leitura consolidada de seis meses;
- o contrato de `GET /api/insights` passou a incluir `largest_expenses` e `monthly_trend`, preservando os campos existentes;

- o contrato de `GET /api/insights` passou a incluir projeção mensal e comprometimento dos cartões, mantendo compatibilidade com os campos da P5.1;
- alertas de vencimento consultam a próxima fatura realmente pendente, separada do ciclo atual exibido pelo cartão;
- o Dashboard consulta o mês completo para projeção, mantendo o realizado limitado ao dia atual pelo backend;
- o Dashboard passou a carregar múltiplos insights do backend e mantém saldo, contas e transações utilizáveis quando a análise automática falha;
- a comparação mensal limita o período atual ao dia presente e usa o intervalo equivalente do mês anterior;
- parcelamentos receberam uma rota própria, acessível diretamente pela sidebar desktop e pelo menu mobile "Mais";
- a navegação inferior mobile prioriza Início, Histórico, criação rápida e Contas, mantendo os demais recursos no menu "Mais";
- modais financeiros ocupam a tela no celular, respeitam safe areas e oferecem uma ação explícita de retorno;
- o histórico deixou de focar e deslocar automaticamente para o formulário; o foco rápido permanece no atalho central `+`;
- o Gate Técnico da Prioridade 2 foi aprovado após 102 testes, build, migrations, verificação do Neon e validação dos fluxos Sandbox em produção; replay externo do mesmo `eventId` e testes independentes permanecem pendentes;
- metadados públicos da API padronizados com a identidade Nivra;
- roadmap do Open Finance reorganizado para integrar contas, saldos e histórico ao núcleo antes dos webhooks;
- todas as APIs protegidas passam a obter o usuário da sessão no backend;
- o frontend deixou de armazenar a identidade autenticada no `localStorage` e de enviar `usuario_id`.
- a confirmação visual do Pluggy Connect agora ocorre somente depois que o backend valida e persiste a conexão.
- dados bancários sincronizados permanecem em tabelas próprias e são combinados com lançamentos manuais na camada de consulta;
- contas manuais preservam seu cálculo de saldo; contas bancárias vinculadas passam a exibir o saldo informado pelo provider.
- o dashboard considera receitas e despesas das contas bancárias vinculadas, ignora duplicações confirmadas e mantém transferências internas neutras.
- alterações bancárias recebidas por webhook atualizam somente os registros indicados; mudanças financeiras relevantes desfazem conciliações antigas para nova revisão.
- o histórico e o dashboard mantêm uma única representação econômica após a conciliação, preservando os registros manual e bancário para auditoria;
- rejeições permanecem válidas em sincronizações comuns, enquanto mudanças econômicas do banco reabrem a decisão.
- transações pertencentes a parcelamentos informam plano, número e total de parcelas e não podem ser alteradas ou excluídas isoladamente.
- parcelas futuras permanecem visíveis no histórico, mas não afetam saldo, entradas, gastos ou economia antes da respectiva data.

### Security

- identidade e permissões da Lumi são definidas exclusivamente pela sessão e
  pelo backend; `usuario_id`, tools e parâmetros arbitrários do cliente são
  rejeitados;
- ausência ou falha da configuração OpenAI afeta somente o endpoint da Lumi e
  não impede a inicialização das demais áreas da Nivra;
- o banco armazena somente hashes dos tokens de sessão;
- logout revoga a sessão no servidor;
- CORS aceita origens locais exatas e origens adicionais configuradas explicitamente.
- troca e recuperação de senha revogam sessões anteriores;
- tokens de conta são persistidos exclusivamente como hashes e não aparecem na URL HTTP;
- respostas de recuperação não confirmam se um e-mail existe.
- `itemId` recebido do frontend é validado diretamente na Pluggy e vinculado ao usuário da sessão por `clientUserId`.
- webhooks usam segredo de no mínimo 32 caracteres comparado em tempo constante, sem sessão, CSRF ou exposição ao frontend.

### Planned

- integração de parcelamentos com cartões/faturas e recorrências pessoais;
- orçamentos e metas financeiras;
- smoke real e multi-turn do provider da Lumi, memória persistente e ações
  financeiras com confirmação em etapas futuras;
- notificações internas, resumos e WhatsApp.

## [0.1.0-alpha.1] - 2026-09-11

> Release notes preparadas para revisão. A tag e a GitHub Release ainda não foram publicadas.

### Added

- interface React e TypeScript com rotas, componentes reutilizáveis e layout responsivo;
- temas claro e escuro;
- backend FastAPI organizado em routers, schemas, services e repositories;
- dashboard com saldo, entradas, gastos e movimentações recentes;
- contas financeiras, saldo calculado e conta principal;
- receitas, despesas e transferências neutras no resumo financeiro;
- categorias, histórico unificado, busca, filtros, criação, edição e exclusão;
- cartões, compras, ciclos de fatura, histórico e pagamento integral;
- PostgreSQL persistente no Neon por SQLAlchemy Core e Psycopg;
- migrations versionadas com Alembic;
- importador seguro e auditável para o SQLite legado;
- configuração integrada de frontend e API para deploy na Vercel;
- testes de regras financeiras, endpoints e isolamento lógico entre usuários.

### Changed

- PostgreSQL substituiu o SQLite como armazenamento oficial da aplicação;
- a identidade pública do produto passou a ser Nivra.

### Security

- credenciais de banco permanecem exclusivamente no backend e em variáveis de ambiente;
- a autenticação atual continua temporária e ainda não é adequada para armazenar dados financeiros críticos.

[Unreleased]: https://github.com/joaordantas/Nivra/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/joaordantas/Nivra/releases/tag/v0.1.0-alpha.1
