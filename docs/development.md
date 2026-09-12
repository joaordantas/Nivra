# Desenvolvimento da Nivra

## Requisitos

- Python 3.12;
- Node.js e npm;
- PostgreSQL acessível;
- Git.

## Backend

Crie o ambiente virtual e instale as dependências:

```bash
python -m venv .venv
pip install -r requirements.txt
```

Defina as variáveis descritas em `.env.example` no seu terminal ou na configuração da IDE. Use valores próprios e nunca versione credenciais.

```text
APP_ENV=development
DATABASE_URL=<conexao PostgreSQL da aplicacao>
DATABASE_URL_UNPOOLED=<conexao direta para migrations>
SESSION_TTL_HOURS=168
CORS_ORIGINS=
APP_PUBLIC_URL=http://127.0.0.1:5173
EMAIL_PROVIDER=memory
PLUGGY_CLIENT_ID=<client id da aplicacao sandbox>
PLUGGY_CLIENT_SECRET=<client secret da aplicacao sandbox>
```

Aplique o schema e inicie a API:

```bash
alembic upgrade head
uvicorn backend.main:app --reload
```

Endereços locais:

- API: `http://127.0.0.1:8000/api`;
- health check: `http://127.0.0.1:8000/api/health`;
- OpenAPI: `http://127.0.0.1:8000/docs`.

## Frontend

```bash
cd frontend
npm ci
npm run dev
```

O Vite inicia normalmente em `http://127.0.0.1:5173`. Quando necessário, `VITE_API_URL` deve conter somente a origem pública da API. Use o mesmo nome de host no frontend e backend durante o desenvolvimento (`127.0.0.1` nos dois, por exemplo) para manter o comportamento de cookies consistente.

O frontend usa `credentials: include`. A sessão fica em cookie HTTP-only, e operações de escrita obtêm automaticamente um token CSRF pelo endpoint `/api/auth/csrf`.

Em desenvolvimento e testes, `EMAIL_PROVIDER=memory` evita entregas externas. Para validar links localmente, os testes usam uma caixa de saída em memória. Em produção, configure `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM` e `APP_PUBLIC_URL`. O remetente deve usar um domínio verificado no provedor.

## Testes

```bash
python -m unittest discover -s tests -v
cd frontend
npm run build
```

A suíte usa `APP_ENV=test` e um banco descartável definido em `TEST_DATABASE_URL`. As proteções impedem que `DATABASE_URL` de produção seja selecionada automaticamente para testes.

## Migrations

```bash
alembic current
alembic upgrade head
alembic revision --autogenerate -m "descricao da alteracao"
alembic check
```

Revise toda migration gerada antes de aplicá-la. Não execute downgrade ou reset contra um banco com dados reais.

## SQLite legado

O arquivo `storage/banco.db` não é o banco oficial. O importador lê esse arquivo sem modificá-lo e exige opções explícitas para gravar ou ignorar os três registros órfãos auditados.

Dry-run:

```bash
python scripts/migrate_sqlite_to_postgres.py --skip-known-orphans
```

Importação deliberada:

```bash
python scripts/migrate_sqlite_to_postgres.py --execute --skip-known-orphans
```

Consulte [o relatório da migração](relatorio-migracao-postgresql.md) antes de executar a importação.

## Deploy na Vercel

Configure no ambiente desejado:

- `APP_ENV`;
- `DATABASE_URL`;
- `DATABASE_URL_UNPOOLED`;
- `SESSION_TTL_HOURS` quando o prazo padrão de 7 dias não for adequado;
- `CORS_ORIGINS` apenas quando existir um frontend confiável em outra origem.
- `APP_PUBLIC_URL=https://nivra-finance.vercel.app`;
- `EMAIL_PROVIDER=resend`;
- `RESEND_API_KEY` com uma chave criada para o projeto;
- `EMAIL_FROM` com um remetente de domínio verificado.
- `PLUGGY_CLIENT_ID` da aplicação Sandbox;
- `PLUGGY_CLIENT_SECRET` da aplicação Sandbox.

As credenciais Pluggy ficam somente no backend e nunca usam o prefixo `VITE_`. Consulte o [guia de ativação do Sandbox](open-finance-sandbox-setup.md) antes do teste publicado.

Em produção, configure `APP_ENV=production`. A Vercel também informa `VERCEL_ENV=production`, usado como proteção adicional para ativar o atributo `Secure` do cookie.

O build integrado instala as dependências do frontend, gera o bundle Vite e publica o FastAPI pelo entrypoint `backend.main:app`. A migration deve ser aplicada de forma controlada antes do primeiro acesso ao banco de um ambiente novo.

## Renomeação dos serviços externos

A troca do nome público no GitHub e na Vercel é uma operação manual e separada do código. Consulte o [guia de renomeação externa](renomeacao-externa.md) antes de alterar qualquer serviço. O projeto Neon já usa o nome `nivra-db` e não precisa ser modificado.

## Convenções

- regras financeiras ficam em services;
- persistência fica em repositories;
- routers não recebem regras de negócio;
- credenciais nunca ficam no frontend;
- funcionalidades futuras não devem ser apresentadas como disponíveis;
- mudanças de schema exigem migration.
