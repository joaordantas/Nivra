# Relatório — Open Finance MVP, Etapa 2B

## Escopo

Esta etapa transforma o sucesso do Pluggy Connect em uma conexão pertencente à Nivra e persistida no PostgreSQL. Ela não importa contas, saldos ou transações, não implementa webhooks e continua limitada ao Sandbox.

## Migration

- revision: `e81f72c4a93b`;
- down revision: `b92d8f3a6c10`;
- aplicada no Neon principal e validada em produção.

A migration cria quatro tabelas:

- `conexoes_bancarias`: proprietário Nivra, provider, Item externo, referência do usuário, instituição, status, ambiente e timestamps;
- `contas_bancarias_externas`: estrutura futura para as contas retornadas pela Pluggy e vínculo opcional com uma conta Nivra;
- `transacoes_bancarias`: estrutura futura com dinheiro em `NUMERIC(14,2)`, data, direção, conciliação e unicidade por conta/ID externo;
- `eventos_sincronizacao`: estrutura futura para execuções, origem, status, contagem e erros sanitizados.

As foreign keys aplicam propriedade e ciclo de vida entre usuário, conexão, contas externas e transações. `UNIQUE(provider, external_item_id)` impede duas conexões Nivra para o mesmo Item. Índices atendem listagem por usuário/status e futuras consultas por conexão/data.

`metadata_provider` usa JSONB no PostgreSQL e JSON compatível nos testes. Nenhum metadata é gravado nesta etapa. O uso futuro será limitado a uma lista explícita de campos necessários; payload completo, credenciais, tokens e documentos não serão persistidos.

## Propriedade e segurança

O Connect Token continua usando `clientUserId = nivra-user-<usuario_id>`, formato já utilizado na Etapa 2A. Ele não contém e-mail, CPF, sessão ou CSRF. `avoidDuplicates` continua habilitado na Pluggy.

Após o callback, o backend recebe somente `item_id`, autentica a sessão, valida CSRF e chama `GET /items/{itemId}` com a API Key da Application Nivra. A resposta precisa:

- existir e ser acessível com a API Key da aplicação;
- repetir exatamente o Item solicitado;
- possuir `clientUserId` do usuário autenticado;
- informar instituição e status válidos;
- ter `executionStatus` `SUCCESS` ou `PARTIAL_SUCCESS`.

O sucesso da consulta com a API Key comprova que o Item pertence à Application da Nivra. O service compara a referência do usuário antes de persistir e repete a validação de proprietário após o insert idempotente. Um usuário não recebe identificador ou instituição quando tenta reivindicar Item alheio.

## API

- `POST /api/open-finance/connect-token`: cria o token temporário;
- `POST /api/open-finance/connections/complete`: valida o Item e finaliza o vínculo;
- `GET /api/open-finance/connections`: lista somente conexões do usuário da sessão.

O callback repetido retorna a conexão existente. A unicidade no banco protege inclusive contra requisições concorrentes. Nenhum endpoint retorna Client ID, Client Secret, API Key, cookie, CSRF ou o Item externo.

## Frontend

O Pluggy Connect só mostra sucesso depois da confirmação do backend. Se a instituição for conectada na Pluggy e a persistência falhar, a interface informa que o vínculo com a Nivra não foi concluído.

A página Contas consulta as conexões persistidas no carregamento e mostra instituição, estado conectado e “Sincronização: Ainda não realizada”. PostgreSQL é a autoridade; `localStorage` e `sessionStorage` não armazenam Item ou estado da conexão.

## Validação

Os testes cobrem provider, normalização do Item, sessão, CSRF, conexão válida, Item inexistente, provider indisponível, estado pendente, callback repetido, idempotência, claim entre usuários, listagem isolada, refresh, logout/login, upgrade, downgrade, foreign keys, constraints e índices.

Resultados da validação em 12 de setembro de 2026:

- suíte Python completa: 65 testes aprovados;
- testes específicos de Open Finance: 13 testes aprovados;
- compilação Python: aprovada;
- build React/TypeScript: aprovado;
- OpenAPI: resposta 200 e rotas das Etapas 2A/2B presentes;
- Alembic em banco descartável: upgrade, downgrade e retorno ao `head` aprovados;
- `alembic check`: nenhuma operação de upgrade ausente;
- geração offline do SQL PostgreSQL: aprovada, incluindo `JSONB` para metadata;
- interface local: validada em 612 px e 1440 px, nos temas claro e escuro;
- persistência visual: conexão restaurada após F5, logout e novo login;
- bundle React: sem Client ID, Client Secret, API Key ou URL PostgreSQL.

Além das validações locais, a Etapa 2B foi ativada e verificada manualmente em produção. A migration foi aplicada no Neon principal, a aplicação foi publicada na Vercel e o fluxo Pluggy Sandbox confirmou: criação do Item, validação server-side, persistência no PostgreSQL, restauração após F5 e após logout/login. A repetição do fluxo não criou uma conexão duplicada.

## Limitações

- somente Pluggy Sandbox;
- sem importação de contas, saldos ou transações;
- sem sincronização manual ou automática;
- sem webhooks, reconexão ou desconexão;
- sem conciliação;
- somente dados Sandbox; nenhuma instituição ou dado bancário real foi habilitado.

## Ativação em produção

O Neon principal está em `e81f72c4a93b`, com as tabelas `conexoes_bancarias`, `contas_bancarias_externas`, `transacoes_bancarias` e `eventos_sincronizacao` confirmadas. O deploy da Vercel está publicado e usa essa estrutura persistente.

Não há migração pendente para a Etapa 2B.

## Referências do provider

- [Create Connect Token](https://docs.pluggy.ai/reference/connect-token-create)
- [Retrieve Item](https://docs.pluggy.ai/reference/items-retrieve)
- [Referencing your user and avoiding duplicates](https://docs.pluggy.ai/docs/item)
