# Relatório — Open Finance MVP, Etapas 2C e 2D

## Escopo entregue

As Etapas 2C e 2D adicionam sincronização manual das conexões Pluggy Sandbox já persistidas pela Nivra. A sincronização recupera a instituição, as contas, os saldos e todas as páginas de transações disponíveis, mantendo esses dados na camada externa criada na Etapa 2B.

Os dados sincronizados não são inseridos em `transacoes` e não alteram saldos de contas Nivra, receitas, despesas, transferências ou o dashboard. A integração com o núcleo financeiro será feita somente na futura conciliação.

## Fluxo

```text
Usuário autenticado
        ↓
POST /api/open-finance/connections/{id}/sync
        ↓
Validação de sessão, CSRF e propriedade
        ↓
Pluggy Item → Accounts → /v2/transactions por cursor
        ↓
Snapshot completo validado em memória
        ↓
Transação atômica no PostgreSQL
        ↓
Upsert de contas e transações + remoção de registros ausentes
        ↓
Evento de sincronização finalizado
```

## Provider

O provider Pluggy passou a normalizar:

- contas `BANK` e `CREDIT`;
- nome, tipo, subtipo, moeda e saldo;
- transações paginadas pelo endpoint `/v2/transactions`;
- descrição, valor financeiro, data, direção e status;
- categoria externa e chave interna Nivra, usando fallback `other`.

A paginação aceita apenas o cursor `after` retornado pela Pluggy e reconstrói a URL sobre o host oficial. Cursores repetidos e mais de 1.000 páginas interrompem a operação com erro controlado.

## Persistência e idempotência

As constraints já criadas na migration `e81f72c4a93b` continuam sendo a base da idempotência:

- `UNIQUE(conexao_id, external_account_id)` para contas;
- `UNIQUE(conta_bancaria_externa_id, external_transaction_id)` para transações.

O repositório usa upsert para criar ou atualizar o mesmo registro externo. Uma nova sincronização:

- não duplica contas ou transações;
- atualiza nome, tipo, saldo, descrição, valor, data, direção e metadata permitida;
- remove transações ausentes do snapshot completo daquela conta;
- remove contas ausentes do snapshot completo e suas transações externas;
- serializa a persistência por conexão no PostgreSQL;
- grava tudo em uma única transação de banco.

As chamadas ao provider acontecem antes da transação de persistência. Se a coleta falhar, o snapshot anterior permanece intacto e um evento de erro sanitizado é registrado.

## API e interface

Foram adicionados:

- `POST /api/open-finance/connections/{connection_id}/sync`;
- `GET /api/open-finance/connections/{connection_id}/accounts`.

A página de Contas agora oferece sincronização manual e mostra:

- data e hora da última sincronização concluída;
- último erro de sincronização, quando houver;
- contas externas importadas;
- saldo informado pelo provider;
- quantidade de transações externas por conta.

## Regressão das categorias e transações

A Etapa 2B.5 permaneceu isolada do cálculo financeiro. O teste de regressão cria uma conta e uma despesa manual, executa a sincronização Open Finance e compara o resumo e o histórico antes e depois. Os valores e lançamentos permanecem iguais.

Categorias externas são registradas apenas como metadata mínima da transação externa. Nenhuma categoria personalizada é renomeada, removida ou utilizada por comparação de texto exibido pelo usuário.

## Validação local

Resultados em 13 de setembro de 2026:

- suíte Python completa: 76 testes aprovados;
- testes de provider: contas e paginação por cursor aprovadas;
- testes de sincronização: primeira importação, re-sync, atualização e exclusão aprovados;
- teste de falha: snapshot anterior preservado e evento de erro registrado;
- teste multiusuário: conexão e contas externas de outro usuário retornam 404;
- teste de regressão financeira: resumo e transações manuais permanecem inalterados;
- build React/TypeScript: aprovado;
- compilação Python: aprovada;
- `git diff --check`: aprovado;
- Alembic: a Etapa 2C/2D reutiliza o schema da Etapa 2B e não exige nova migration.

## Ativação no Neon e na Vercel

A migration das categorias padrão foi aplicada no Neon principal em 13 de setembro de 2026:

```powershell
$env:APP_ENV = "production"
$env:DATABASE_URL_UNPOOLED = "<URL direta do Neon>"
.venv\Scripts\python.exe -m alembic upgrade head
```

O Neon foi confirmado no `head` `c64e8a1f9b2d`. As Etapas 2C/2D não exigiram outra migration nem novas variáveis de ambiente.

O commit `405e7cd` foi publicado na branch `main` e implantado pela Vercel. Em produção foram confirmados:

- `/api/health` com resposta HTTP 200;
- `/openapi.json` com resposta HTTP 200 e as rotas novas de sincronização;
- login da conta de teste e restauração da sessão após atualizar a página;
- criação e persistência de uma conexão Pluggy Bank pelo Connect Sandbox PF;
- importação de 2 contas externas: Conta Corrente e Mastercard Black;
- importação de 41 transações, sendo 25 da Conta Corrente e 16 do Mastercard Black;
- saldos externos de R$ 36.180,75 e -R$ 961,95 exibidos pelo frontend;
- segunda sincronização mantendo 41 transações, sem duplicação;
- atualização da página restaurando conexão, saldos e as mesmas contagens pelo backend;
- transações manuais da Nivra preservadas e visíveis no dashboard antes e depois da ativação.

As credenciais `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, `DATABASE_URL` e `DATABASE_URL_UNPOOLED` continuam exclusivamente no backend/Vercel. Nenhum valor real deve ser colocado no repositório.

## Limitações preservadas

- somente Pluggy Sandbox;
- sincronização iniciada manualmente;
- sem webhooks;
- sem sincronização automática;
- sem reconexão ou desconexão;
- sem conciliação com lançamentos manuais;
- sem inclusão dos dados externos no dashboard financeiro.

## Próxima unidade lógica

Etapa 2D.5 — integração Open Finance com o núcleo da Nivra.

A ordem foi revista depois da validação em produção. A sincronização já mantém contas, saldos e transações externas com segurança, mas esses dados ainda ficam separados de `contas`, `transacoes` e do dashboard. Automatizar novas sincronizações por webhook antes de tornar os dados úteis no núcleo teria pouco valor perceptível para testers.

A Etapa 2D.5 deverá:

- usar `contas_bancarias_externas.conta_nivra_id` para criar ou vincular contas;
- tratar o saldo do provider como fonte atual das contas vinculadas;
- construir um histórico unificado por consulta, sem copiar cegamente registros externos;
- resolver categorias pela chave interna criada na Etapa 2B.5;
- identificar a origem `Manual` ou `Banco`;
- aplicar uma conciliação básica antes de incluir os dados no dashboard;
- impedir dupla contagem de saldos e movimentações.

Webhooks passam a ser a Etapa 2E seguinte. A conciliação mais sofisticada permanece na Etapa 2H.
