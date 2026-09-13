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

## Ativação manual no Neon e na Vercel

Antes do deploy, aplicar a migration pendente das categorias padrão:

```powershell
$env:APP_ENV = "production"
$env:DATABASE_URL_UNPOOLED = "<URL direta do Neon>"
.venv\Scripts\python.exe -m alembic upgrade head
```

O `head` esperado é `c64e8a1f9b2d`. Não é necessário criar tabelas ou variáveis adicionais para as Etapas 2C/2D.

Depois, publicar o código na Vercel e validar com uma conta de teste:

1. entrar na Nivra;
2. abrir Contas;
3. manter ou criar uma conexão Sandbox PF;
4. clicar em **Sincronizar**;
5. confirmar contas, saldos e quantidades de transações;
6. clicar novamente e confirmar que não aparecem registros duplicados;
7. atualizar a página e confirmar que os dados continuam disponíveis.

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

Etapa 2E — webhooks seguros e idempotentes da Pluggy.
