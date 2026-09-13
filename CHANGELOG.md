# Changelog

Todas as alterações importantes da Nivra serão documentadas neste arquivo. O formato segue os princípios do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/) durante sua evolução pré-1.0.

## [Unreleased]

### Added

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

### Changed

- metadados públicos da API padronizados com a identidade Nivra;
- roadmap do Open Finance reorganizado para integrar contas, saldos e histórico ao núcleo antes dos webhooks;
- todas as APIs protegidas passam a obter o usuário da sessão no backend;
- o frontend deixou de armazenar a identidade autenticada no `localStorage` e de enviar `usuario_id`.
- a confirmação visual do Pluggy Connect agora ocorre somente depois que o backend valida e persiste a conexão.
- dados bancários sincronizados permanecem em tabelas próprias e são combinados com lançamentos manuais na camada de consulta;
- contas manuais preservam seu cálculo de saldo; contas bancárias vinculadas passam a exibir o saldo informado pelo provider.
- o dashboard considera receitas e despesas das contas bancárias vinculadas, ignora duplicações confirmadas e mantém transferências internas neutras.
- alterações bancárias recebidas por webhook atualizam somente os registros indicados; mudanças financeiras relevantes desfazem conciliações antigas para nova revisão.

### Security

- o banco armazena somente hashes dos tokens de sessão;
- logout revoga a sessão no servidor;
- CORS aceita origens locais exatas e origens adicionais configuradas explicitamente.
- troca e recuperação de senha revogam sessões anteriores;
- tokens de conta são persistidos exclusivamente como hashes e não aparecem na URL HTTP;
- respostas de recuperação não confirmam se um e-mail existe.
- `itemId` recebido do frontend é validado diretamente na Pluggy e vinculado ao usuário da sessão por `clientUserId`.
- webhooks usam segredo de no mínimo 32 caracteres comparado em tempo constante, sem sessão, CSRF ou exposição ao frontend.

### Planned

- parcelamentos e recorrências pessoais;
- orçamentos e metas financeiras;
- motor determinístico de insights e área “Sua atenção”;
- Lumi, a assistente financeira da Nivra;
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
