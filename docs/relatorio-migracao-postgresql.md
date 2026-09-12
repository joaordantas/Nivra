# Relatório da migração para PostgreSQL

Data: 11 de setembro de 2026

## Resultado

O PostgreSQL passa a ser o banco oficial do backend. A aplicação lê `DATABASE_URL`, mantém as credenciais somente no FastAPI e não usa mais o arquivo SQLite como persistência em produção. O schema deixou de ser criado no startup e agora evolui por migrations Alembic.

A integração com um projeto Neon real ainda depende da criação do banco e do cadastro das URLs no ambiente local e na Vercel. Nenhuma credencial foi inventada ou incluída no repositório.

## Abordagem escolhida

Foi adotado SQLAlchemy Core com SQL textual parametrizado, driver Psycopg 3 e Alembic. Essa combinação mantém os repositories atuais e evita uma reescrita arriscada para ORM. Um adaptador central converte os placeholders legados para parâmetros nomeados, normaliza datas e valores retornados e concentra as diferenças permitidas do SQLite de teste.

SQLite continua disponível somente quando `APP_ENV=test` e `TEST_DATABASE_URL` está definida. Fora dos testes, uma URL SQLite é recusada. Isso permite testes rápidos sem manter duas implementações de repositories.

Dependências adicionadas:

- `SQLAlchemy`: engine, pool, tipos e metadata;
- `psycopg[binary]`: driver PostgreSQL;
- `alembic`: migrations versionadas.

## Conexões e ambiente serverless

O engine fica em cache durante a vida de uma instância aquecida da função. A configuração usa `pool_pre_ping`, reciclagem de conexões, pool local pequeno e timeout curto. `DATABASE_URL` deve usar a URL pooled do Neon. Alembic e o importador preferem `DATABASE_URL_UNPOOLED`, evitando executar operações de manutenção pelo pooler quando a URL direta está disponível.

Variáveis:

```text
APP_ENV=development | production | test
DATABASE_URL=<URL PostgreSQL pooled>
DATABASE_URL_UNPOOLED=<URL PostgreSQL direta, recomendada para migrations>
TEST_DATABASE_URL=<banco exclusivo de teste>
```

## Schema e migrations

A migration inicial é `13ecd0272470_initial_postgresql_schema.py`. Ela cria o schema atual completo, incluindo as estruturas que já existiam antes desta tarefa. Nenhuma nova funcionalidade da Fase 3 foi criada.

Principais decisões:

- dinheiro em `NUMERIC(14, 2)`;
- datas financeiras em `DATE`;
- estados ativos/principal em `BOOLEAN`;
- foreign keys para usuários, contas, categorias, transações, transferências e estruturas existentes;
- checks para valores positivos, tipos de transação e contas distintas em transferências;
- constraint única para conta principal ativa por usuário;
- índices compostos em consultas por usuário e data e índices nas foreign keys consultadas com frequência;
- IDs continuam inteiros gerados por sequence no PostgreSQL.

O arquivo antigo `database/schema.py` foi removido porque alterava o schema durante o import do backend. A API agora presume que `alembic upgrade head` foi executado previamente.

## Repositories e regras financeiras

Os repositories continuam sendo a camada de persistência. Foram removidos `lastrowid`, `INSERT OR IGNORE`, `COLLATE NOCASE`, `strftime`, datas relativas do SQLite, booleanos inteiros e `BEGIN IMMEDIATE`.

Os inserts que precisam devolver ID usam `RETURNING id`. Comparações de nomes usam `LOWER`, períodos são calculados em Python e a consulta de limites usa uma expressão compatível com PostgreSQL e SQLite de teste.

A troca de conta principal bloqueia a linha do usuário com `FOR UPDATE` no PostgreSQL e permanece protegida por índice único parcial. O pagamento de fatura bloqueia a fatura e grava o pagamento em uma única transação. Transferências continuam sendo um único registro atômico e não entram como receita ou despesa.

Os services continuam validando propriedade por `usuario_id`. O teste de integração confirmou que um segundo usuário não consegue registrar movimentações em conta de outro usuário nem listar seus dados.

## Migração dos dados antigos

O script `scripts/migrate_sqlite_to_postgres.py`:

- usa `storage/banco.db` em modo somente leitura;
- analisa tabelas e relacionamentos antes de conectar ao destino;
- exige `--execute` para gravar;
- exige `--skip-known-orphans` para deixar fora somente os três registros auditados;
- compara todos os campos desses registros com uma assinatura versionada;
- interrompe a operação se aparecer qualquer órfão novo ou se um registro conhecido mudar;
- exige que o destino esteja na migration esperada;
- recusa destino com dados por padrão;
- preserva IDs e reseta sequences;
- importa na ordem das foreign keys;
- executa toda a cópia em uma transação;
- não apaga nem modifica o SQLite;
- com `--allow-existing`, só ignora uma linha existente se todos os seus dados forem equivalentes; conflitos encerram a operação.

O dry-run no banco atual encontrou:

```text
transacoes.id=1 → usuario_id=1 ausente
transacoes.id=2 → usuario_id=2 ausente
vendas.id=2     → usuario_id=1 ausente
```

Esses registros já estavam órfãos no SQLite. A decisão aprovada foi mantê-los somente no SQLite original, sem criar usuários fictícios e sem enfraquecer as foreign keys. O banco original e seus arquivos auxiliares foram preservados. O comando `--skip-known-orphans` autoriza apenas essas três linhas exatas; qualquer alteração no conteúdo ou qualquer novo órfão bloqueia a importação.

Com essa opção, o banco atual possui 21 registros válidos para importação e 3 registros ignorados:

```text
transacoes: 8 válidas, 2 ignoradas
vendas:     1 válida, 1 ignorada
demais tabelas: 12 válidas, 0 ignoradas
total: 21 válidas, 3 ignoradas
```

## Testes executados

- 29 testes Python: aprovados;
- fluxo HTTP de cadastro e login: aprovado;
- criação e listagem isolada de dois usuários: aprovada;
- conta, categoria, receita, despesa e transferência: aprovadas;
- edição e exclusão: aprovadas;
- regras de saldo e transferências: aprovadas;
- regressão das estruturas já existentes da Fase 3A: aprovada;
- proteção contra uso de banco de produção em testes: aprovada;
- detecção de registros órfãos no importador: aprovada;
- autorização restrita aos três órfãos conhecidos: aprovada;
- bloqueio de órfão novo e de registro conhecido alterado: aprovado;
- hash SHA-256 do SQLite antes e depois do dry-run: idêntico;
- migration aplicada repetidamente em bancos de teste limpos: aprovada;
- DDL PostgreSQL gerado em modo offline pelo Alembic: aprovado;
- compilação de todos os módulos Python: aprovada;
- build React/TypeScript/Vite: aprovado, 1.901 módulos transformados;
- FastAPI iniciado localmente: aprovado;
- `/api/health`: HTTP 200 e banco online no ambiente isolado;
- `/docs` e `/openapi.json`: HTTP 200.

Não havia PostgreSQL ou Docker instalado localmente, e nenhuma URL Neon foi fornecida. Por isso, a conexão de rede com um PostgreSQL real, a execução da migration no Neon, a importação efetiva e o teste após redeploy permanecem como validações manuais dependentes do ambiente externo.

## Arquivos principais criados

- `.env.example`;
- `alembic.ini`;
- `database/models.py`;
- `database/migrations.py`;
- `migrations/env.py`;
- `migrations/script.py.mako`;
- `migrations/versions/13ecd0272470_initial_postgresql_schema.py`;
- `scripts/migrate_sqlite_to_postgres.py`;
- `tests/db_support.py`;
- `tests/test_api_phase2.py`;
- `tests/test_database_config.py`;
- `tests/test_sqlite_migration.py`.

Arquivos principais alterados:

- conexão e health check do backend;
- repositories de usuários, categorias, contas, transações, transferências, limites, vendas e cartões existentes;
- tratamento de integridade nos routers;
- hash de senha armazenado como texto bcrypt portátil;
- testes antigos, requirements, pyproject, gitignore e README.

## Passos manuais no Neon e na Vercel

1. Criar um projeto PostgreSQL no Neon.
2. Copiar a URL pooled para `DATABASE_URL` e a URL direta para `DATABASE_URL_UNPOOLED`.
3. Definir localmente `APP_ENV=development` e as duas URLs.
4. Executar `alembic upgrade head`.
5. Executar `python scripts/migrate_sqlite_to_postgres.py --skip-known-orphans` e conferir os 21 registros válidos e os 3 ignorados.
6. Executar `python scripts/migrate_sqlite_to_postgres.py --execute --skip-known-orphans` somente depois dessa conferência.
7. No painel da Vercel, cadastrar `APP_ENV=production`, `DATABASE_URL` e `DATABASE_URL_UNPOOLED` nos ambientes desejados.
8. Fazer o deploy e conferir `/api/health`.
9. Executar o roteiro de persistência e isolamento descrito no README.

## Limitações conhecidas

> Atualização posterior: esta limitação histórica foi resolvida pela autenticação server-side. O frontend não envia mais `usuario_id`; a identidade atual vem da sessão HTTP-only validada pelo backend. Consulte `docs/relatorio-autenticacao-segura.md` e `docs/relatorio-hardening-autenticacao.md`.

Nenhuma alteração funcional da Fase 3A foi desenvolvida durante esta migração.
