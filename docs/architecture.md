# Arquitetura da Nivra

## Visão geral

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

O frontend não acessa o PostgreSQL diretamente. Toda leitura ou alteração passa pela API e pelas regras de negócio do backend.

## Responsabilidades

### Frontend

O diretório `frontend/` contém a interface React, navegação, formulários, feedbacks e temas. O acesso HTTP está centralizado em `frontend/src/services/api.ts`.

### Routers

`backend/routers/` define os endpoints sob `/api`, recebe schemas validados e converte resultados ou erros para respostas HTTP. Uma dependência compartilhada autentica a sessão e entrega o usuário atual às rotas protegidas. Routers devem permanecer pequenos.

### Schemas

`backend/schemas/` define contratos de entrada e saída com Pydantic. Essa camada impede que formatos inválidos avancem para as regras financeiras.

### Services

`services/` concentra validações, propriedade dos dados e regras financeiras. Transferências, por exemplo, permanecem neutras no resumo de receitas e despesas.

### Repositories

`repositories/` executa consultas, inserts, updates e deletes. As consultas sempre recebem o contexto do usuário quando a entidade é privada.

### Database

`database/` centraliza engine, conexões, tipos e metadata. PostgreSQL é o banco oficial; Alembic mantém o schema versionado em `migrations/`.

## Persistência e serverless

O backend usa a conexão PostgreSQL fornecida por `DATABASE_URL`. Em Vercel, a aplicação usa a URL pooled do Neon e mantém um pool local pequeno por instância aquecida. Migrations e importações podem usar `DATABASE_URL_UNPOOLED`.

A API não cria tabelas no startup e não depende de arquivos locais para persistência. O SQLite permanece apenas como origem legada e banco descartável de testes.

## Atomicidade

Operações críticas utilizam transações. A troca de conta principal serializa alterações concorrentes, pagamentos de fatura bloqueiam a linha correspondente e uma transferência é persistida como um único evento entre contas.

## Autenticação e isolamento

O login cria uma sessão persistente no PostgreSQL. O navegador recebe um identificador aleatório em cookie HTTP-only; o banco guarda somente seu hash. Em produção, o cookie usa `Secure` e `SameSite=Lax`. A sessão possui prazo de expiração configurável e o logout a revoga no servidor.

Verificação de e-mail e recuperação de senha usam tokens aleatórios de uso único. O link carrega o token no fragmento da URL, evitando que ele seja enviado no caminho HTTP, e o PostgreSQL recebe somente o SHA-256. A alteração ou recuperação de senha revoga sessões e tokens ainda ativos. Uma nova sessão é criada apenas para o dispositivo que alterou a senha autenticado.

Limites de tentativa são compartilhados entre instâncias serverless por meio da tabela `auth_rate_events`. As chaves combinam contexto de rede e identidade normalizada e são persistidas somente como hash. Na Vercel, o backend usa o endereço de cliente informado pelos cabeçalhos controlados pela plataforma.

O frontend não envia `usuario_id` nas APIs protegidas. O FastAPI resolve `current_user` a partir da sessão, as rotas repassam essa identidade e os services verificam a propriedade de contas, categorias, transações, transferências, cartões e demais entidades privadas. Requisições de alteração também exigem um token CSRF vinculado à sessão.

O histórico e o gerenciamento individual de dispositivos permanecem no roadmap de segurança.

## Evolução planejada

As próximas capacidades devem reutilizar services e repositories existentes. Lumi consumirá funções financeiras bem definidas; não terá acesso SQL direto. Notificações serão baseadas em eventos financeiros e canais desacoplados.
