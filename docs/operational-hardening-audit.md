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
