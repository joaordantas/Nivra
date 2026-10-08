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
