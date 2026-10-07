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

## Notificações financeiras

O recálculo autenticado de insights produz os fatos canônicos de fatura,
comprometimento de cartão e gasto fora do padrão. Depois do cálculo, uma camada
única de producers converte apenas os fatos elegíveis em templates de
notificação e os entrega ao `NotificationService`. Chamadas internas ao service
de insights não emitem notificações por padrão; o router de insights habilita o
efeito de forma explícita no fluxo operacional do usuário.

Cada notificação é persistida em transação própria, fora das transações
financeiras. Falhas são registradas somente com producer, tipo e resultado e
não invalidam o insight nem revertem uma operação financeira já concluída. A
unicidade por usuário e chave de evento faz replay e concorrência convergirem
para uma única notificação lógica.

As preferências financeiras ficam em `notification_preferences`, com chave
composta por usuário e identificador fechado. A ausência de registro significa
habilitada, preservando o comportamento dos usuários que nunca configuraram a
funcionalidade. O producer carrega o estado efetivo uma vez por lote e descarta
eventos desabilitados antes de chamar o `NotificationService`. Um ledger técnico
em `notification_preference_suppressions` conserva apenas a chave dos eventos
observados enquanto desativados, impedindo que reapareçam como backfill após a
reativação. Notificações já persistidas não são alteradas.

Leitura e atualização usam a identidade da sessão. A alteração parcial exige
CSRF, aceita apenas os seis booleanos conhecidos e não permite que o frontend
informe um usuário ou uma categoria arbitrária.

### Resumos financeiros periódicos

`PeriodicFinancialSummaryService` produz resumos semanais e mensais sem expor
um endpoint HTTP. O chamador fornece a data civil de referência e pode fornecer
explicitamente o início do período, o que mantém testes e uma futura integração
com scheduler determinísticos. A semana é de segunda a domingo e o mês é civil;
somente períodos integralmente encerrados são aceitos. A aplicação continua
adotando as datas civis persistidas pelo domínio financeiro, sem inferir o fuso
do servidor nem introduzir configuração de timezone por usuário nesta fase.

A fonte da verdade é a agregação canônica dos insights: transações manuais e de
Open Finance reconciliadas, transferências internas neutras excluídas e compras
de cartão contabilizadas na data da compra. Pagamentos de fatura não viram uma
segunda despesa. As consultas são limitadas por usuário e pelas datas do período
atual/anterior; não há leitura do histórico completo nem N+1 por lançamento.

Sem atividade não há notificação. Com atividade, o template determinístico usa
entradas, despesas, saldo líquido, maior categoria válida e comparação de
despesas quando o período anterior possui base diferente de zero. A chave
`tipo_do_resumo + início_do_período`, protegida pela unicidade já existente no
banco, garante idempotência em replay e concorrência. `weekly_summary` e
`monthly_summary` são habilitadas por padrão e reutilizam o mesmo ledger de
supressões, portanto um período observado enquanto desabilitado não reaparece
após reativação. A metadata contém apenas rota, tipo e início do período. Ao
ativar uma notificação, o frontend aceita somente uma allowlist fixa de rotas
internas existentes; os resumos direcionam para `/dashboard`.

### Agendamento dos resumos periódicos

O agendamento foi preparado para o modelo serverless atual. Um Vercel Cron
diário deverá fazer `GET /api/internal/jobs/periodic-summaries`; a rota, oculta
do OpenAPI, autentica `Authorization: Bearer <CRON_SECRET>`, rejeita parâmetros
e payload e entrega ao runner somente a data civil calculada no timezone fixo
da aplicação. O segredo é exclusivo do scheduler. CSRF protege sessões de
navegador e, por isso, não substitui a autenticação máquina-a-máquina desta
rota.

`PeriodicSummaryJobRunner` é independente do trigger HTTP. Ele seleciona
somente a última semana e o último mês integralmente encerrados, pagina IDs de
usuários por chave crescente, renova uma lease curta por lote e processa cada
usuário em transação própria pelo `PeriodicFinancialSummaryService`. O runner
não contém agregação financeira, preferência ou lógica do ledger. Ausência de
atividade e supressão são resultados operacionais normais.

`periodic_summary_job_runs` combina tracking e lock distribuído. A constraint
única por tipo e início do período impede dois donos lógicos; um token protege
renovação/finalização e a expiração de quinze minutos permite recuperação após
crash. Execuções com falha ou sucesso parcial podem ser retomadas até quatro
tentativas de job. Operações transitórias por usuário têm até três tentativas,
com backoff limitado de 250 e 500 ms. A idempotência das notificações continua
sendo a segunda camada de proteção quando uma retomada reavalia usuários já
concluídos.

O scheduler diário não percorre histórico arbitrário: cada execução considera
apenas o período semanal e mensal imediatamente anteriores à data injetada.
Assim, uma chamada perdida pode ser recuperada enquanto aquele período ainda é
o último encerrado; períodos mais antigos exigem decisão operacional explícita.
Logs e tracking contêm tipo, período, status, duração e contadores, sem IDs de
usuário, PII, valores ou conteúdo financeiro.

A execução permanece desativada por padrão. Importar a aplicação não inicia
threads nem jobs; `PERIODIC_SUMMARY_JOBS_ENABLED=true` é obrigatório para uma
execução real. A CLI operacional oferece referência fixa, seleção de tipo,
tamanho de lote e dry-run. A configuração do Vercel Cron não integra esta fase,
portanto nenhum deploy ou agendamento de Production foi alterado. O runbook
completo está em `docs/periodic-summary-jobs.md`.

## Orçamentos mensais canônicos

O domínio de orçamentos segue `budgets` → `BudgetRepository` →
`BudgetService` → API autenticada → tela `/budgets`. Cada registro possui ID
persistido e combina usuário, categoria de despesa e primeiro dia do mês com
unicidade no banco. Categoria e período formam a identidade financeira e são
imutáveis; a atualização altera somente o limite. Exclusão remove apenas o
planejamento e nunca movimentações financeiras. Categorias em uso por um
orçamento não podem ser excluídas.

O limite usa `NUMERIC(14,2)`/`Decimal`, deve ser positivo e é exposto pela API
como decimal exato. O período público usa `AAAA-MM`, convertido pelo service
para uma data no primeiro dia do mês. A leitura e correção do limite histórico,
assim como a preparação de meses futuros, são permitidas. No mês atual, lançamentos posteriores à data
civil de referência ainda não entram no consumo.

`BudgetService` reutiliza a agregação econômica dos insights em uma única
passagem por usuário e período: transações manuais, movimentos Open Finance não
duplicados, compras de cartão na data da compra e parcelas nas datas aplicáveis.
Transferências internas e pagamentos de fatura não são novas despesas. O
repository de orçamento não consulta transações. `spent`, `remaining` e
`usage_percentage` são calculados com `Decimal`; o percentual não é limitado a
100%, embora a barra visual seja limitada para não causar overflow.

A API oferece `GET/POST /api/budgets`, `GET/PATCH/DELETE
/api/budgets/{id}`. A listagem exige ou assume um mês e não carrega o histórico
inteiro. O usuário vem exclusivamente da sessão; mutações exigem CSRF, toda
consulta filtra ownership e uma categoria privada de outro usuário é rejeitada.

A migration `c2d3e4f5a6b7` substitui `limites` por `budgets`, preservando ID,
usuário, categoria, mês e precisão dos registros válidos. Período inválido,
valor não monetário ou categoria de outro usuário interrompem a migration com
erro explícito; nada é descartado ou inventado. A tabela antiga é removida após
a cópia, portanto não existe dual-write. Orçamento global, rollover, forecast,
metas e alertas permanecem fora deste domínio. A futura P7.7 deverá consumir o
contrato do `BudgetService`, sem recalcular gastos.

## Autenticação e isolamento

O login cria uma sessão persistente no PostgreSQL. O navegador recebe um identificador aleatório em cookie HTTP-only; o banco guarda somente seu hash. Em produção, o cookie usa `Secure` e `SameSite=Lax`. A sessão possui prazo de expiração configurável e o logout a revoga no servidor.

Verificação de e-mail e recuperação de senha usam tokens aleatórios de uso único. O link carrega o token no fragmento da URL, evitando que ele seja enviado no caminho HTTP, e o PostgreSQL recebe somente o SHA-256. A alteração ou recuperação de senha revoga sessões e tokens ainda ativos. Uma nova sessão é criada apenas para o dispositivo que alterou a senha autenticado.

Limites de tentativa são compartilhados entre instâncias serverless por meio da tabela `auth_rate_events`. As chaves combinam contexto de rede e identidade normalizada e são persistidas somente como hash. Na Vercel, o backend usa o endereço de cliente informado pelos cabeçalhos controlados pela plataforma.

O frontend não envia `usuario_id` nas APIs protegidas. O FastAPI resolve `current_user` a partir da sessão, as rotas repassam essa identidade e os services verificam a propriedade de contas, categorias, transações, transferências, cartões e demais entidades privadas. Requisições de alteração também exigem um token CSRF vinculado à sessão.

O histórico e o gerenciamento individual de dispositivos permanecem no roadmap de segurança.

## Open Finance Sandbox

O frontend solicita um Connect Token temporário ao backend e abre o Pluggy Connect. O token é criado com uma referência interna estável no formato `nivra-user-<usuario_id>` e com prevenção de duplicidade habilitada. Credenciais permanentes, API Key e segredos da Pluggy permanecem no backend.

Quando o widget conclui uma conexão, o frontend envia somente o `itemId` para `POST /api/open-finance/connections/complete`. O backend consulta o Item diretamente na Pluggy com a API Key da aplicação, compara o `clientUserId` com o usuário da sessão e somente então grava a referência em `conexoes_bancarias`. A consulta server-side também comprova que o Item está acessível à Application da Nivra.

O PostgreSQL aplica unicidade por provider e Item, e o service rejeita tentativas de reivindicar uma conexão de outro usuário. `GET /api/open-finance/connections` sempre filtra pelo usuário autenticado e restaura o estado após refresh ou novo login.

Contas, saldos e transações do Sandbox são persistidos em `contas_bancarias_externas` e `transacoes_bancarias`. Uma conta externa pode ser vinculada a uma conta Nivra; nesse caso, o saldo informado pelo provider é a fonte do saldo atual e o histórico combina os lançamentos bancários e manuais sem copiar cegamente os dados externos para `transacoes`.

A conciliação compara somente movimentos do mesmo usuário e da mesma conta vinculada, com direção e valor idênticos e diferença máxima de dois dias. A descrição normalizada aumenta a confiança, sem ser requisito. `correspondencias_conciliacao` preserva candidatos, confiança, motivos e decisões. Confirmações mantêm os dois registros físicos, mas a consulta financeira exibe e contabiliza um único evento. Rejeições não reaparecem em uma sincronização comum; alterações de valor, data, direção ou restauração da transação bancária reabrem a análise. Exclusões externas são arquivadas e não removem o lançamento manual.

Webhooks usam um segredo exclusivo no backend e uma caixa de entrada idempotente por `eventId`. Eventos suportados atualizam somente a conexão pertencente ao Item recebido; eventos informativos desconhecidos são reconhecidos e ignorados sem derrubar a integração. O ambiente permanece limitado ao Pluggy Sandbox.

## Evolução planejada

As próximas capacidades devem reutilizar services e repositories existentes. Lumi consumirá funções financeiras bem definidas; não terá acesso SQL direto. Notificações serão baseadas em eventos financeiros e canais desacoplados.
