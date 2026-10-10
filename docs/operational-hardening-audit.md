# Auditoria de consolidação operacional

## Enquadramento oficial

O roadmap não define P7.8 nem P9.1. P7.1–P7.7 já compõem o sistema de
notificações e P8.1/P8.2 são seus domínios financeiros canônicos. Portanto, este
trabalho é registrado como **Prioridade 9 — Gate de consolidação operacional de
notificações**, sem criar numeração nova.

## Classificação do roadmap

| Área | Classificação | Evidência ou pendência |
| --- | --- | --- |
| P1–P5 | implementada | core financeiro, segurança, Open Finance e parcelamentos cobertos pelo produto e regressão |
| P6.1–P6.9 | implementada com rollout restrito | arquitetura e gates concluídos; testers externos e rollout público dependem de decisão humana |
| P7.1–P7.7 | implementada | centro, preferências, produtores, resumos, scheduler e alertas canônicos presentes |
| P8.1/P8.2 financeiros | implementada | budgets e goals são fontes canônicas consumidas pela P7.7 |
| WhatsApp | adiada | integração, consentimento e canais externos não pertencem a este gate |
| Prioridade 9 | parcialmente implementada | este gate fecha operação de notificações; hardening transversal, LGPD e testes públicos continuam pendentes |
| Prioridade 10 | futura | escopo Nivra Pro não iniciado |

## Lacunas encontradas e decisão

| Lacuna | Risco | Tratamento |
| --- | --- | --- |
| dedupe dependia da linha visível | retenção/exclusão permitia replay antigo | ledger durável transacional e backfill por migration |
| sem política executável de retenção | crescimento indefinido | limpeza em lotes, somente lidas, prazos explícitos e flag off |
| tracking não separava gerar/deduplicar | diagnóstico ambíguo | contadores persistidos e logs estruturados |
| sem visão rápida do último estado | investigação exigia SQL manual | CLI `status` somente leitura |
| alertas e limpeza sem trigger serverless | operação manual apenas | endpoints internos protegidos, ainda sem cron |
| SDK bancário no chunk inicial | custo para rotas sem Open Finance | lazy loading da tela de contas |
| roadmap P7.3 desatualizado | divergência documental | itens de budgets/goals reconciliados com P7.7 |

O build de referência tinha chunk inicial de 519,67 kB. Após isolar a rota de
contas, o chunk inicial ficou em 396,22 kB (redução aproximada de 23,8%) e o
chunk sob demanda da tela/SDK bancário ficou em 121,06 kB. O warning de chunk
inicial acima de 500 kB deixou de ocorrer.

## Limites conscientes

Não foram ativados cron, Preview, Production, Lumi, `FINANCIAL_ALERTS_ENABLED`
ou canais externos. Não foram escolhidos prazos reais de retenção. Backup global,
restauração, LGPD, error boundaries, rate limit geral, WhatsApp, Nivra Pro e
rollout público da Lumi continuam fora do escopo ou dependem de decisão humana.

## Evidência do gate

- backend: 401 testes e 83 subtests aprovados;
- frontend: 32 testes aprovados, typecheck e build Vite aprovados;
- Python: compilação dos módulos aprovada;
- migration head: `f5a6b7c8d9e0`, com `alembic check` sem operações;
- PostgreSQL descartável: upgrade, concorrência com oito runners, retenção,
  dedupe pós-limpeza, ausência de efeitos financeiros, downgrade, reupgrade e
  remoção do banco isolado aprovados;
- bundle: chunk inicial reduzido de 519,67 kB para 396,22 kB.

Resultado técnico: **APROVADO**. A ativação permanece bloqueada por decisões de
política e ambiente, não por falha de implementação.

## Gate de prontidão operacional e Preview — 8 de outubro de 2026

A reauditoria começou com árvore limpa no commit `bf8b10c`. O remoto `main`
estava em `2aab7b4`; o último Preview registrado, em `e2d968a`. Esse Preview é
ancestral do commit local e não contém os dez commits P7/P8/P9 seguintes. A
consulta somente leitura aos bancos candidatos confirmou revisions antigas,
sem `notification_dedupe_ledger` e sem as três colunas novas do tracking.

O Preview respondeu com a página de login da Vercel, não com JSON da aplicação.
Sem CLI autenticada ou vínculo local do projeto, não foi possível confirmar as
variáveis de ambiente do deployment. Por segurança, nenhum trigger, migration,
status ou dry-run foi enviado ao Preview. Production recebeu apenas um GET de
health público e permaneceu inalterada.

Em ambiente isolado, 44 testes direcionados e 26 subtests passaram antes da
correção; os testes diretamente afetados passaram novamente depois dela. A
regressão final aprovou 401 testes e 83 subtests de backend, 32 testes frontend,
typecheck/build Vite, compilação Python e `alembic check`. O gate PostgreSQL
descartável repetiu migration, concorrência de oito runners, dedupe, preservação
de não lidas, ausência de efeito financeiro, downgrade e reupgrade. A CLI
`status` e o dry-run retornaram código zero no banco descartável. Durante a
revisão, o cutoff de notificações lidas foi corrigido para usar `lida_em`,
evitando expiração imediata de uma notificação antiga lida recentemente.

Classificação: **APROVADO COM RESSALVAS**. A prontidão local e em PostgreSQL
descartável está comprovada. A observação em Preview continua pendente por
defasagem de código/schema, proteção de acesso e ausência de autorização para
push, deploy ou migration. A política de retenção proposta ainda requer decisão
humana e avaliação jurídica/LGPD.

## Validação final e preparação do piloto — 9 de outubro de 2026

### Classificação

**APROVADO COM RESSALVAS PARA PREPARAÇÃO DO PILOTO.** O Preview correto está
implantado, isolado e com schema atual; as verificações seguras e somente leitura
foram concluídas. O encerramento da Prioridade 9 permanece condicionado a login
por credenciais, teste multiusuário real e execução da CLI contra a branch atual,
todos dependentes de acesso ou escrita remota ainda não autorizados. A execução
de jobs não integra esta autorização e continua bloqueada.

### Deployment, banco e configuração

- branch implantada: `codex/p7-1-notification-foundation`;
- commit implantado: `7c0aace70f512e7ecaa159be764f004fcfeac8b3`;
- deployment Vercel: Ready, ambiente Preview, ID sanitizado
  `BGabSpPziUrCZ6ogtyRVoYCWq6jb`;
- projeto Neon: `nivra-preview`, branch `br-empty-salad-b6i0j70t`, exclusiva do
  Preview inspecionado;
- migration instalada: `f5a6b7c8d9e0`;
- a branch contém um usuário, um orçamento e uma meta; nenhuma notificação,
  preferência, entrada de dedupe, estado de alerta ou execução de job;
- `PERIODIC_SUMMARY_JOBS_ENABLED`, `FINANCIAL_ALERTS_ENABLED`,
  `NOTIFICATION_MAINTENANCE_ENABLED` e `CRON_SECRET` não estão definidos para o
  Preview atual, mantendo os gatilhos em fail-closed;
- `LUMI_PUBLIC_ENABLED` não está definido para esta branch;
- variáveis de banco existem separadamente para Preview e Production; valores
  secretos não foram revelados nem copiados;
- nenhum push, deploy, migration, alteração de variável ou acesso a Production
  foi realizado nesta etapa.

### Testes concluídos

- backend direcionado: **60/60 aprovados** em 145,058 s, cobrindo autenticação,
  CSRF, IDOR/BOLA, orçamentos, metas, notificações, preferências, deduplicação,
  triggers internos, manutenção, CLIs e retenção;
- frontend: **32/32 aprovados**;
- build Vite: aprovado, 1.945 módulos transformados, chunk inicial de 396,22 kB
  e chunk lazy de contas de 121,06 kB;
- migration completa até `f5a6b7c8d9e0` exercitada pelos testes direcionados;
- nenhuma correção de código foi necessária e nenhum teste falhou.

### Auditoria da diferença 401 versus 397

A descoberta padrão atual (`unittest discover -s tests`) encontra **397 casos**.
A mesma estrutura de testes existe no commit anterior usado pelo relatório: o
diff até o commit atual altera somente expectativas de retenção em dois arquivos
e não remove nem adiciona métodos de teste ou classes `TestCase`. Também não há
`load_tests` customizado. Existem dez gates PostgreSQL como scripts de integração
fora do padrão `test*.py`, portanto não entram nessa descoberta.

Não foi encontrada evidência reproduzível para os **401** registrados
historicamente, nem comando ou decomposição que explique quatro casos extras.
A conclusão suportada pelas evidências é que 401 foi uma inconsistência de
contagem/documentação, e não perda de descoberta, parametrização ou cobertura.
O número canônico para a suíte descoberta atualmente é 397; gates externos e
subtests devem ser reportados separadamente.

### Preview: status, dry-run, logs e métricas

Uma consulta estritamente somente leitura foi executada no console da branch
Preview e confirmou migration, contadores operacionais, últimos jobs e candidatos
à retenção proposta. Resultado sanitizado:

| Indicador | Resultado |
| --- | ---: |
| usuários | 1 |
| notificações / não lidas | 0 / 0 |
| preferências / ledger de dedupe / estados financeiros | 0 / 0 / 0 |
| orçamentos / metas | 1 / 1 |
| jobs totais / em execução / falhos / retries | 0 / 0 / 0 / 0 |
| candidatos: lidas há mais de 180 dias | 0 |
| candidatos: histórico de jobs há mais de 180 dias | 0 |

Isso constitui um **status real e um dry-run SQL real contra o Preview**, sem
escrita e sem limpeza. A execução dos comandos da CLI da aplicação contra essa
mesma branch ainda não ocorreu: não há no workspace uma credencial válida para o
endpoint atual nem vínculo local do projeto. Duas URLs locais antigas apontam
para outros endpoints e foram deliberadamente rejeitadas.

Os logs do deployment inspecionado não apresentaram eventos Warning, Error ou
Fatal na janela disponível; também não havia novas requisições de função nessa
janela. Como não houve job, não há amostra real de retry ou métricas de produtor
no Preview. Os contadores persistidos estão íntegros e zerados.

### Autenticação, logout, CSRF, IDOR e multiusuário

- acesso não autenticado a `/dashboard` redireciona para `/login` no Preview;
- a sessão de teste anterior foi encerrada, confirmando o retorno ao login;
- CSRF, troca de identidade por `user_id` forjado e IDOR/BOLA entre contas foram
  aprovados na regressão direcionada;
- endpoints de criação arbitrária e triggers administrativos públicos permanecem
  ausentes ou protegidos, conforme os testes;
- não havia credenciais autorizadas disponíveis e a branch possui somente um
  usuário. Assim, **login por credenciais e isolamento multiusuário real no
  Preview não foram executados** para contas, orçamentos, metas e notificações;
- nenhum usuário ou dado sintético foi criado sem autorização.

### Validação mobile automatizada

A página pública de login do Preview foi validada em viewports exatos de 375,
390 e 430 px, todos com altura de 844 px. Nos três casos, título e formulário
ficaram visíveis, os sete controles interativos ficaram dentro da área horizontal
e não houve overflow horizontal. O documento declara viewport responsivo com
`width=device-width, initial-scale=1.0`.

Esta evidência cobre a tela de login em navegador automatizado. Ela **não cobre
as telas autenticadas e não substitui teste em dispositivo físico**.

### Política de retenção proposta — não ativada

1. notificações lidas: elegíveis 180 dias após `lida_em`;
2. notificações não lidas: preservadas;
3. histórico de jobs: elegível após 180 dias, preservando execuções ativas e a
   evidência operacional mínima definida pelo runbook;
4. logs sanitizados: retenção proposta de 30 dias;
5. ledger durável de deduplicação e estados financeiros: não entram na limpeza
   de notificações, para impedir replay e preservar a máquina de estados.

Os prazos continuam pendentes de aprovação de produto/operação e revisão
jurídica/LGPD. A flag de manutenção permanece desativada e nenhuma limpeza real
foi executada.

### Procedimento preparado para o piloto manual

**Pré-condições e escopo**

1. obter autorização para dois usuários de teste e dados exclusivamente
   sintéticos, todos identificados pelo prefixo `P9-PILOT-20261009`;
2. obter credencial temporária e exclusiva da branch Preview atual, mantida apenas
   no processo local e nunca registrada no repositório ou no relatório;
3. registrar baseline sanitizado de migration, contagens, flags, jobs, ledger e
   estados financeiros;
4. manter Cron, Lumi pública e todos os produtores desativados.

**Validação funcional e de isolamento**

1. autenticar usuário A e usuário B, validar renovação de sessão e logout;
2. criar, somente após autorização, uma conta, orçamento, meta, categoria e
   transações sintéticas por usuário;
3. confirmar que listagens e detalhes retornam apenas o tenant autenticado;
4. tentar ler e alterar IDs do outro usuário e registrar apenas status HTTP e IDs
   sanitizados; o resultado esperado é 403/404 sem vazamento de existência;
5. repetir mutações sem token CSRF válido e confirmar rejeição;
6. verificar central de notificações e preferências sem acionar produtores.

**Execução manual de jobs — autorização separada**

1. escolher um único produtor e um período sintético;
2. habilitar somente sua flag no Preview e provisionar segredo temporário do
   trigger, sem criar agendamento;
3. executar uma vez, capturar run ID, contadores, ledger e notificação resultante;
4. repetir exatamente o mesmo período e confirmar ausência de duplicata por
   `already_completed` ou dedupe durável;
5. desabilitar a flag imediatamente; somente depois, e com nova autorização,
   repetir para o produtor seguinte;
6. nunca executar limpeza durante o piloto.

**Rollback e evidências**

- primeiro rollback: desabilitar/remover flags e segredo do Preview e interromper
  novas chamadas;
- remover apenas registros com o namespace do piloto, após autorização específica
  para essa exclusão; nunca modificar os registros financeiros já existentes;
- se houver anomalia estrutural, preservar evidências e avaliar restore point da
  branch Neon antes de qualquer restauração;
- registrar horários UTC, deployment/commit, status HTTP, IDs de run sanitizados,
  contagens antes/depois e prova de dedupe, sem cookies, tokens, e-mails ou dados
  financeiros detalhados.

### Ações que exigem autorização

1. criar dois usuários de teste e os registros sintéticos namespaced no Preview;
2. remover exclusivamente esses registros ao final do piloto;
3. criar ou fornecer uma credencial temporária da branch atual para executar a
   CLI real de `status` e `cleanup --dry-run`;
4. configurar segredo e flag de um produtor no Preview;
5. executar cada job manual, um de cada vez.

Os itens 4 e 5 exigem autorização separada no momento da execução. Eles não são
necessários para concluir login, multiusuário ou a CLI somente leitura.

### Prontidão para encerrar a Prioridade 9

O código, deployment, schema, configuração fail-closed, testes locais, consulta
operacional somente leitura e plano de piloto estão prontos. A Prioridade 9 ainda
não deve ser encerrada até concluir: (a) login real com credenciais autorizadas,
(b) isolamento multiusuário no Preview, (c) telas autenticadas em 375/390/430 px
e (d) comandos reais da CLI contra a branch atual. A Prioridade 10 permanece não
iniciada.

## Execução autorizada do piloto funcional — 9 de outubro de 2026

Esta seção substitui as quatro pendências de encerramento listadas acima. A
execução permaneceu limitada ao Preview, sem jobs, alteração de flags, Cron,
Lumi pública, limpeza de retenção, push ou deploy.

### Usuários e dados sintéticos

Foram criados os usuários `P9-PILOT-20261009-A` e
`P9-PILOT-20261009-B`, cada um com:

- uma conta manual própria;
- um orçamento de Alimentação próprio para outubro de 2026;
- uma meta financeira própria;
- uma despesa manual própria, de R$ 20,00 para A e R$ 30,00 para B.

Uma preferência de alertas de orçamento foi desativada somente para A. Em B, a
mesma preferência permaneceu ativada, comprovando persistência por usuário. A
consulta final somente leitura ao Neon confirmou: 2 usuários, 2 contas, 2
orçamentos, 2 metas, 2 transações, 1 linha de preferência, 0 notificações e 0
entradas no ledger de deduplicação associados ao namespace do piloto.

Após confirmação final, a limpeza remota foi executada em transação protegida.
A inspeção das dependências revelou 40 categorias padrão criadas automaticamente
com os dois usuários. As duas primeiras tentativas foram integralmente revertidas
ao encontrar vínculos `NO ACTION`/`RESTRICT`; portanto, não deixaram alterações
parciais. A transação concluída exigiu, antes de apagar, exatamente 2 usuários,
2 transações, 2 contas, 2 orçamentos, 40 categorias e zero registros nas demais
tabelas financeiras sem cascata. Em seguida removeu os registros filho nessa
ordem e os dois usuários exatos, permitindo que metas, preferência, sessões,
tokens e demais vínculos em cascata fossem eliminados.

A verificação posterior confirmou zero registros para os IDs 2 e 3 em usuários,
contas, categorias, orçamentos, metas, transações, preferências, notificações,
ledger de deduplicação, sessões e tokens. A linha de base do Preview retornou a
1 usuário, 1 orçamento, 1 meta e 20 categorias. Ao recarregar o dashboard que
mantinha a sessão B, a aplicação redirecionou para a tela de login, comprovando
a invalidação da sessão. Nenhum registro preexistente foi incluído.

### Autenticação e isolamento real

- cadastro, sessão inicial, logout e novo login por credenciais foram aprovados
  para A e B;
- após login como B, contas, orçamentos e metas de A não foram exibidos;
- após novo login como A, contas, orçamento, meta e transação de B não foram
  exibidos;
- os orçamentos calcularam separadamente R$ 20,00 de R$ 200,00 para A e R$ 30,00
  de R$ 300,00 para B;
- o dashboard de B apresentou saldo de R$ 1.970,00, despesa recente própria e
  análises derivadas somente de seus dados;
- a central de notificações permaneceu vazia, coerente com produtores desativados,
  e indicou zero não lidas para ambos os usuários;
- a regressão direcionada de 60 testes continua sendo a evidência de requisições
  forjadas de CSRF e IDOR/BOLA. A tentativa adicional de abrir diretamente um ID
  de A com a sessão B foi bloqueada pelo próprio cliente de automação antes de
  chegar à aplicação; portanto, não é registrada como resposta do backend.

### CLI real no Preview

A connection string existente da branch atual foi copiada com a senha mascarada,
usada somente em memória e removida do ambiente e do clipboard ao final. Nenhum
arquivo local ou variável Vercel foi criado.

O comando direto por caminho revelou uma limitação de invocação local
(`ModuleNotFoundError` para `repositories`). A forma correta por módulo foi então
executada e aprovada:

- `python -m scripts.run_notification_maintenance status`:
  `status=ok`, `latest_runs=[]`;
- `python -m scripts.run_notification_maintenance cleanup --read-days 180
  --job-days 180 --dry-run`: `status=dry_run`, `reason=validated`,
  `processed=0`, `generated=0`, `failed=0`, `retries=0`, duração de 234 ms.

O dry-run não gerou tracking, notificações ou exclusões.

### Mobile autenticado

Dashboard, contas, transações, orçamentos, metas e configurações foram validados
com sessão B em viewports exatos de 375, 390 e 430 px, todos com altura de 844
px. Em todas as combinações:

- `window.innerWidth` correspondeu ao tamanho solicitado;
- não houve overflow horizontal;
- nenhum controle interativo visível ficou cortado horizontalmente;
- os títulos das páginas carregadas foram identificados;
- a central de notificações ocupou exatamente a largura do viewport e permaneceu
  integralmente visível.

O teste automatizado não substitui validação em dispositivo físico.

### Resultado atualizado e pendências

Classificação mantida: **APROVADO COM RESSALVAS**. Login, logout, sessão,
isolamento multiusuário, persistência de preferências, funções financeiras,
mobile autenticado, CLI real contra o Preview e limpeza integral dos dados
sintéticos estão comprovados. Permanecem:

1. executar teste manual em dispositivo físico quando houver disponibilidade;
2. executar requisição IDOR remota forjada com ferramenta HTTP autenticada, se
   for exigida evidência adicional além da regressão e do isolamento funcional;
3. aprovar formalmente a política 180/180/30 antes de qualquer ativação;
4. autorizar separadamente cada produtor e job do piloto operacional.

A política 180/180/30 foi posteriormente aprovada para o piloto, sem ativação de
limpeza ou Cron. A regressão final passou de 397 para 401 casos por quatro novos
testes de hardening (paginação/isolamento, cabeçalhos, limite geral e sanitização
de paths); a execução canônica aprovou 401/401. O frontend aprovou 37/37 e o
build de produção, com bundle inicial de 403,99 kB (118,35 kB gzip).

Foram adicionados paginação/filtros server-side do histórico, rate limiting
geral, logs correlacionados, cabeçalhos defensivos, `no-store`, error boundary,
skip link, onboarding, páginas públicas de privacidade/termos e runbook de
backup/recuperação. Um runner de piloto foi preparado com trava de host Preview,
usuário sintético exclusivo, lote restrito e limpeza protegida. A conexão local
legada não corresponde à branch atual, portanto nenhuma execução foi atribuída
ao banco incorreto.

**Classificação de encerramento: APROVADO COM RESSALVAS NÃO BLOQUEANTES.** As
ressalvas são revisão jurídica do texto público, captura editorial de screenshots
e teste futuro em aparelho físico. Production, main, Cron, Lumi pública e os
produtores de Production permaneceram inalterados. A Prioridade 10 permanece não
iniciada.
