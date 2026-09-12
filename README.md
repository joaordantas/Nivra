<div align="center">

# NIVRA

**Controle financeiro inteligente, simples e automatizado.**

A Nivra está sendo desenvolvida para tornar o controle financeiro mais rápido, claro e progressivamente automatizado.

[![Status](https://img.shields.io/badge/status-alpha-6D5DFB)](#status-do-projeto)
[![React](https://img.shields.io/badge/React-18-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-persistente-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Neon](https://img.shields.io/badge/Neon-database-00E599?logo=neon&logoColor=black)](https://neon.tech/)
[![Vercel](https://img.shields.io/badge/Vercel-deploy-000000?logo=vercel&logoColor=white)](https://vercel.com/)

[Aplicação online](https://nivra-finance.vercel.app) · [Roadmap](docs/roadmap.md) · [Arquitetura](docs/architecture.md) · [Desenvolvimento](docs/development.md) · [Release notes](docs/releases/v0.1.0-alpha.1.md) · [Releases](https://github.com/joaordantas/Nivra/releases)

</div>

## Sobre a Nivra

A Nivra é uma plataforma de finanças pessoais em evolução. Seu objetivo é reduzir o tempo gasto organizando movimentações, consultando saldos e tentando descobrir o que merece atenção.

O produto parte de um núcleo financeiro funcional e avança gradualmente para automação, insights e orientação em linguagem natural. A proposta é oferecer mais contexto e clareza sem transformar a rotina financeira em trabalho manual constante.

> **Seu dinheiro. Mais claro. Menos trabalho.**

## Filosofia do produto

- menos trabalho manual, cliques e digitação;
- informações importantes fáceis de encontrar;
- contexto para entender receitas, gastos e saldos;
- automação introduzida de forma gradual e verificável;
- alertas úteis no momento certo;
- regras financeiras centralizadas e previsíveis.

## O que já funciona

### Finanças pessoais

- Dashboard com saldo, entradas, gastos e movimentações recentes;
- contas financeiras com saldo inicial e saldo calculado;
- definição de conta principal;
- receitas e despesas vinculadas a contas e categorias;
- transferências entre contas, neutras no cálculo de receitas e despesas;
- histórico unificado de movimentações;
- busca e filtros por tipo, conta, categoria e período;
- criação, edição e exclusão com recálculo dos saldos;
- categorias gerenciadas nas configurações e durante o registro;
- cartões, compras, ciclos de fatura, histórico e pagamento integral;
- interface responsiva para desktop e dispositivos móveis;
- temas claro e escuro.

### Plataforma

- frontend React, TypeScript e Vite;
- rotas reais com React Router;
- API REST em FastAPI;
- separação entre routers, schemas, services e repositories;
- PostgreSQL persistente no Neon;
- acesso ao banco por SQLAlchemy Core e Psycopg;
- migrations versionadas com Alembic;
- configuração de deploy integrado na Vercel;
- sessões persistentes no PostgreSQL com cookie HTTP-only;
- proteção CSRF nas operações de escrita;
- identidade do usuário determinada pelo backend;
- testes de regras financeiras, API, falsificação de identidade e isolamento entre usuários.
- verificação de e-mail com link de uso único;
- alteração e recuperação de senha com revogação das sessões anteriores;
- limites persistentes para tentativas de login, cadastro e recuperação.

## Demonstração e screenshots

A aplicação já possui telas funcionais, mas as capturas públicas ainda não foram preparadas. A estrutura em [`docs/assets/screenshots`](docs/assets/screenshots/README.md) está reservada para imagens revisadas e sem dados pessoais.

| Tela | Captura pública |
| --- | --- |
| Dashboard | Pendente |
| Transações | Pendente |
| Contas | Pendente |
| Cartões e faturas | Pendente |
| Experiência mobile | Pendente |

A aplicação está disponível no [domínio de produção confirmado na Vercel](https://nivra-finance.vercel.app).

## ✦ Lumi — em desenvolvimento

**Lumi** será a assistente financeira inteligente da Nivra. Ela está planejada para aplicar linguagem natural aos services financeiros existentes, oferecendo consultas e ações com confirmação.

Exemplos planejados:

```text
Quanto gastei com alimentação este mês?
Estou gastando mais que no mês passado?
Registre R$ 42,90 de iFood.
Quanto da minha próxima fatura já está comprometido?
Posso gastar R$ 300 este final de semana?
```

Lumi ainda não está implementada. O motor determinístico de insights, o contexto financeiro e as operações seguras serão construídos antes da integração com IA.

## Arquitetura

```text
                 Nivra
                   │
          React + TypeScript
                   │
                REST /api
                   │
                FastAPI
                   │
                Services
                   │
              Repositories
                   │
           SQLAlchemy Core
                   │
          PostgreSQL / Neon
```

- **Frontend:** apresenta os dados, formulários, estados e navegação.
- **Routers:** expõem os contratos HTTP e convertem erros de aplicação.
- **Schemas:** validam entradas e respostas da API.
- **Services:** concentram regras financeiras, validações e propriedade dos dados.
- **Repositories:** executam consultas e persistência.
- **Database:** gerencia conexão, modelos de schema e migrations.

Detalhes estão em [Arquitetura](docs/architecture.md).

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Interface | React 18, TypeScript, Vite, React Router, Lucide React |
| API | Python 3.12, FastAPI, Pydantic |
| Persistência | PostgreSQL, Neon, SQLAlchemy Core, Psycopg 3 |
| Schema | Alembic |
| Hospedagem | Vercel |
| Testes | unittest, FastAPI TestClient, banco isolado |

## Roadmap

| Marco | Situação |
| --- | --- |
| Fundação React e interface responsiva | Concluído |
| Núcleo de contas e movimentações | Concluído |
| PostgreSQL persistente e migrations | Concluído |
| Conta principal, cartões e faturas | Disponível em Alpha |
| Autenticação segura e hardening de conta | Concluído |
| Parcelamentos e recorrências | Planejado |
| Orçamentos e metas | Planejado |
| Open Finance | Planejado |
| Insights financeiros | Planejado |
| Lumi | Em desenvolvimento conceitual |
| Notificações e WhatsApp | Planejado |

Consulte o [roadmap público](docs/roadmap.md) para todos os marcos.

## Status do projeto

> [!WARNING]
> A Nivra está em **Alpha**. Embora a identidade já seja validada por sessão segura no backend, outras camadas de segurança, operação e funcionalidades financeiras ainda estão em evolução. Esta versão não é recomendada para armazenar informações financeiras críticas.

O backend identifica o usuário pelo cookie HTTP-only, consulta a sessão persistida no PostgreSQL e injeta essa identidade nas rotas protegidas. O React não escolhe nem envia `usuario_id`. Alterações exigem um token CSRF vinculado à sessão, e o logout revoga a sessão no servidor.

## Instalação local

Requisitos:

- Python 3.12;
- Node.js e npm;
- banco PostgreSQL acessível;
- variáveis de ambiente configuradas.

Backend:

```bash
python -m venv .venv
pip install -r requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Por padrão, o frontend local acessa `http://127.0.0.1:8000/api`. A documentação OpenAPI fica em `http://127.0.0.1:8000/docs`.

O guia completo está em [Desenvolvimento local](docs/development.md).

## Configuração

Use [`.env.example`](.env.example) apenas como referência. Credenciais reais devem permanecer no ambiente local ou no provedor de hospedagem.

| Variável | Uso |
| --- | --- |
| `APP_ENV` | Identifica desenvolvimento, teste ou produção |
| `DATABASE_URL` | Conexão PostgreSQL usada pela aplicação |
| `DATABASE_URL_UNPOOLED` | Conexão direta para migrations e importação |
| `TEST_DATABASE_URL` | Banco isolado e descartável para testes |
| `SESSION_TTL_HOURS` | Prazo da sessão; o padrão é 168 horas |
| `CORS_ORIGINS` | Origens adicionais confiáveis, separadas por vírgula |
| `VITE_API_URL` | Origem pública da API, quando frontend e backend não compartilham domínio |
| `APP_PUBLIC_URL` | URL pública usada nos links de verificação e recuperação |
| `EMAIL_PROVIDER` | Provedor de entrega; atualmente `resend` em produção |
| `RESEND_API_KEY` | Credencial do Resend, somente no backend |
| `EMAIL_FROM` | Remetente pertencente a um domínio verificado |

Variáveis que contêm credenciais de banco nunca devem usar o prefixo `VITE_`.

## Banco de dados

PostgreSQL é o armazenamento oficial, atualmente fornecido pelo Neon. O SQLite foi usado no desenvolvimento inicial e permanece apenas como fonte legada de migração e banco isolado em testes.

O schema é aplicado com Alembic e não é recriado durante o startup da API. Consulte o [relatório da migração PostgreSQL](docs/relatorio-migracao-postgresql.md) para decisões, validações e procedimento do importador legado.

## Deploy

O repositório está preparado para compilar o frontend Vite e publicar a API FastAPI na Vercel. Em produção, a função recebe as conexões PostgreSQL por variáveis de ambiente e não depende do filesystem para persistência.

Antes do primeiro deploy de um ambiente novo:

1. configure `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `APP_ENV=production` e, se necessário, `CORS_ORIGINS` na Vercel;
2. aplique `alembic upgrade head` ao banco correspondente;
3. publique o commit desejado;
4. confirme `/api/health`, cadastro, login e persistência após um novo deploy.

## Segurança e limitações

- sessões ficam no PostgreSQL; somente o hash do token de sessão é armazenado;
- o cookie da sessão é HTTP-only, SameSite Lax e Secure em produção;
- operações de escrita exigem proteção CSRF vinculada à sessão;
- a identidade vem do backend e a propriedade continua validada nos services;
- tokens de verificação e recuperação expiram, são de uso único e ficam armazenados somente como hash;
- troca e recuperação de senha revogam as sessões anteriores;
- tentativas sensíveis possuem limites persistentes no PostgreSQL;
- histórico e gerenciamento individual de dispositivos ainda estão planejados;
- filtros são processados no frontend e ainda não possuem paginação no backend;
- Lumi, insights automáticos e notificações ainda não estão disponíveis;
- a aplicação permanece em Alpha e não deve receber dados financeiros críticos.

Nenhuma credencial PostgreSQL é enviada ao React. O fluxo permanece navegador → FastAPI → PostgreSQL.

## Releases e versionamento

A primeira release pública está preparada como **`v0.1.0-alpha.1` — Core Finance**, mas ainda não foi publicada. Consulte as [release notes](docs/releases/v0.1.0-alpha.1.md) e o [changelog](CHANGELOG.md).

O projeto usará versões pré-1.0 enquanto autenticação, planejamento, inteligência e automação amadurecem. Nenhuma fase interna corresponde diretamente a uma versão pública.

## Autor

Desenvolvido por **João Dantas** — [@joaordantas](https://github.com/joaordantas).
