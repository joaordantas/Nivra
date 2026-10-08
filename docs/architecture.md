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
metas e alertas permanecem fora deste domínio. A P7.7 consome o contrato do
`BudgetService`, sem recalcular gastos.

## Metas financeiras canônicas

O domínio de metas usa `goals` e `goal_movements` → `GoalRepository` →
`GoalService` → API autenticada → tela `/goals`. A categoria textual `goal` das
memórias da Lumi continua sendo apenas memória explícita e não participa deste
domínio. Cada meta possui ID estável, nome, descrição opcional, alvo
`NUMERIC(14,2)`, prazo opcional e ciclo `active`/`archived`.

O valor reservado não é armazenado na meta: ele é derivado em lote como aportes
efetivos menos retiradas efetivas. Movimentos futuros permanecem no histórico,
mas só afetam o progresso na data civil aplicável. Retiradas são serializadas
por lock da meta e uma simulação cronológica impede saldo negativo, inclusive
quando inseridas retroativamente. Uma chave de idempotência opcional por usuário
torna retries seguros. Movimentos não são editados ou excluídos; correções devem
usar lançamentos compensatórios.

`saved_amount`, `remaining_amount` e `progress_percentage` usam `Decimal`.
Progresso pode superar 100%; conclusão é derivada e pode ser revertida por uma
retirada, sem se confundir com arquivamento. Alterar o alvo recalcula o estado.
Metas vazias podem ser excluídas; metas com histórico são arquivadas, preservando
todos os movimentos.

Aportes e retiradas são reservas lógicas. Eles não alteram contas, saldos,
transações, cartões, faturas, Open Finance ou a agregação econômica. A interface
e a API deixam explícito que o valor reservado não comprova disponibilidade em
uma conta bancária.

A API oferece `GET/POST /api/goals`, `GET/PATCH/DELETE /api/goals/{id}` e
`GET/POST /api/goals/{id}/movements`. O usuário vem somente da sessão, mutações
exigem CSRF e recursos estrangeiros retornam ausência. A migration
`d3e4f5a6b7c8` parte do domínio de orçamentos e não transforma memórias da Lumi.
Este é o segundo pré-requisito financeiro da P7.7. Producers e limiares de
notificação não pertencem à P8.2; são integrados pela seção P7.7 abaixo.

## Alertas canônicos de orçamentos e metas

A P7.7 conecta os domínios financeiros já existentes ao mesmo centro interno
de notificações: `BudgetService`/`GoalService` →
`FinancialThresholdAlertService` → `NotificationService` → tabela
`notifications`. Não há um segundo feed, cálculo financeiro paralelo, envio a
IA ou canal externo.

Orçamentos usam o consumo mensal oficial do `BudgetService`. O maior limiar
alcançado em cada avaliação é 80% (`warning`) ou 100% (`critical`); o percentual
real continua visível quando existe overspend. Metas ativas usam o progresso
oficial do `GoalService`, considerando somente movimentos efetivos, nos marcos
50%, 75% e 100%. Os três marcos de meta usam severidade informativa, com 100%
apresentado como conclusão. Reservas continuam lógicas e não afetam contas ou
transações.

`financial_alert_states` guarda apenas usuário, tipo/ID da fonte, identidade do
período e maior marco processado. A chave de notificação é determinística e a
unicidade existente em `(usuario_id, chave_dedupe)` torna retries e concorrência
seguros. Regressão de consumo, retirada ou aumento do alvo não reduz o marco;
por isso uma nova subida não repete alertas antigos. Cada mês de orçamento tem
identidade própria. Alterações que saltam vários níveis publicam somente o mais
alto. Metas arquivadas são ignoradas, e a reativação apenas estabelece a linha
de base corrente.

As preferências `budget_threshold` e `goal_progress` são habilitadas por padrão.
Quando desabilitadas, o evento é registrado como suprimido e o marco é
consumido; reativar a preferência não produz histórico atrasado. Na primeira
reconciliação, fontes preexistentes também são apenas baselined, evitando uma
tempestade retroativa.

Operações canônicas de orçamento e meta executam avaliação best-effort depois
do commit quando existe ponto seguro. Falha de notificação nunca reverte a
operação financeira. Uma reconciliação diária cobre transações, cartões,
parcelas e Open Finance: o runner usa paginação keyset, lotes, retry limitado e
o mesmo claim/lease persistente da P7.6 sob o tipo `financial_alerts`. A CLI é
`python -m scripts.run_financial_alert_jobs`; `FINANCIAL_ALERTS_ENABLED=true` é
obrigatório para escrita. A flag fica desligada por padrão, nenhum endpoint
público dispara o job e nenhum cron de Production foi configurado.

A migration `e4f5a6b7c8d9` amplia as constraints de preferências e jobs e cria o
estado mínimo de marcos. O custo operacional é uma leitura agregada de
orçamentos do mês e uma de metas por usuário, mais escritas somente ao avançar
marcos ou estabelecer baseline. A limitação atual é operacional: a frequência
real da reconciliação depende de ativação externa futura; não existem e-mail,
WhatsApp ou push nesta fase.

## Consolidação operacional das notificações

A migration `f5a6b7c8d9e0` separa a idempotência da vida útil da notificação
visível. `notification_dedupe_ledger` registra somente usuário, chave técnica e
instante de criação. A criação reserva a chave e insere a notificação na mesma
transação; exclusão manual ou retenção remove apenas a apresentação. Por isso,
um replay antigo permanece deduplicado mesmo quando a linha visível já não
existe. O ledger só é removido pela cascata de exclusão do próprio usuário.

A manutenção usa o mesmo claim, token, lease, limite de tentativas e recovery de
`periodic_summary_job_runs`, sob o tipo `cleanup`. Apenas notificações lidas e
anteriores ao cutoff explicitamente configurado são removidas em lotes. Linhas
não lidas, preferências, supressões, estados de orçamento/meta e todas as tabelas
financeiras ficam fora do alcance. No tracking, somente execuções terminais
antigas que possuam uma execução posterior do mesmo tipo são elegíveis; a mais
recente de cada tipo e qualquer execução em andamento são preservadas.

O tracking também registra `generated_count`, `deduplicated_count` e
`duration_ms`. Logs de jobs usam dimensões fechadas, sem identidade, conteúdo de
notificação ou valores financeiros. A CLI de manutenção oferece status somente
leitura e dry-run. Os triggers internos de alertas e manutenção reutilizam
`CRON_SECRET`, recusam parâmetros/payload, não aparecem no OpenAPI e permanecem
fechados por flags independentes. Nenhuma agenda é iniciada no processo HTTP.

### Topologia observada no gate de prontidão

Em 8 de outubro de 2026, o commit local `bf8b10c` ainda não existia no remoto.
O último deployment Preview registrado apontava para `e2d968a`, dez commits
atrás e anterior à fundação P7. Os dois endpoints Neon identificados localmente
como Preview estavam em `b5c7d9e1f203` e `d7e8f9a012b3`; ambos não possuíam o
ledger ou as colunas de observabilidade. A URL do deployment era protegida pelo
login da Vercel e não permitiu observar a API sem credencial administrativa.

O health público de Production permaneceu apenas em leitura e informou um
fingerprint de banco diferente dos candidatos Preview. Isso comprova distinção
dos endpoints observados, mas não substitui a confirmação do vínculo efetivo na
Vercel. Consequentemente, status, dry-run e migration não foram executados em
Preview. O gate operacional real requer primeiro deployment autorizado do SHA,
vínculo explícito ao banco isolado e snapshot anterior à migration.

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
