# Operação segura de notificações

## Estado entregue

Os jobs semanal, mensal, de alertas financeiros e de manutenção compartilham o
tracking persistente, claim atômico, lease renovável, recovery após expiração e
limite de quatro claims por período. Todos continuam desligados por padrão. Esta
entrega não adiciona agenda ao `vercel.json`, não altera Preview ou Production e
não autoriza uma ativação.

## Política de retenção

A aplicação não escolhe prazos em nome de produto, privacidade ou jurídico. Uma
execução real exige, simultaneamente:

- `NOTIFICATION_MAINTENANCE_ENABLED=true`;
- `NOTIFICATION_READ_RETENTION_DAYS` entre 1 e 3.650;
- `NOTIFICATION_JOB_RETENTION_DAYS` entre 1 e 3.650;
- batch entre 1 e 1.000; o padrão técnico é 250.

Somente notificações **lidas** anteriores ao cutoff são removidas. Notificações
não lidas não expiram. A manutenção não lê nem altera contas, transações,
cartões, faturas, budgets, goals ou movimentos; também preserva preferências,
eventos suprimidos, estados de marcos e o ledger durável de deduplicação.

O histórico de jobs só perde linhas terminais antigas quando existe uma linha
mais nova do mesmo tipo. A última execução de cada tipo, jobs em andamento e a
própria execução corrente são preservados. A limpeza é idempotente e processada
em lotes curtos.

## Inspeção e dry-run

Consultar o último estado de cada tipo não exige habilitar escrita:

```powershell
.venv\Scripts\python.exe -m scripts.run_notification_maintenance status
```

Simular a política conta candidatos sem apagar dados ou criar tracking:

```powershell
.venv\Scripts\python.exe -m scripts.run_notification_maintenance cleanup --dry-run --reference 2026-10-08 --read-days 90 --job-days 180
```

Uma execução manual real deve ocorrer primeiro em ambiente descartável ou
Preview, depois de aprovação explícita dos prazos:

```powershell
$env:NOTIFICATION_MAINTENANCE_ENABLED = "true"
$env:NOTIFICATION_READ_RETENTION_DAYS = "90"
$env:NOTIFICATION_JOB_RETENTION_DAYS = "180"
.venv\Scripts\python.exe -m scripts.run_notification_maintenance cleanup --reference 2026-10-08
```

Os números acima são apenas exemplos de comando, não recomendação de política.

## Métricas e logs

Cada execução expõe e persiste período, status, tentativa, duração, processados,
sucessos, suprimidos, ignorados, falhas, retries, geradas e deduplicadas. Para o
job `cleanup`, `success` representa notificações removidas e `skipped` representa
linhas históricas de job removidas; o log nomeia ambas explicitamente.

Os logs não incluem usuário, e-mail, título, mensagem, descrição, valor ou
payload financeiro. Alertas mínimos:

- `failed` ou `partial_success` em qualquer job;
- `attempt_limit` ou `lock_conflict` recorrente;
- duração ou retries crescendo em execuções sucessivas;
- ausência de execução além da agenda aprovada;
- volume de deduplicadas inesperadamente maior que geradas.

## Triggers internos preparados

Os endpoints abaixo são `GET`, ocultos do OpenAPI, autenticados com
`Authorization: Bearer <CRON_SECRET>` e recusam query string ou payload:

- `/api/internal/jobs/periodic-summaries`;
- `/api/internal/jobs/financial-alerts`;
- `/api/internal/jobs/notification-maintenance`.

Cada domínio ainda exige sua própria flag. A manutenção também exige os dois
prazos. Configuração ausente ou inválida responde de forma sanitizada e não
executa. Não use sessão de usuário, `usuario_id` ou segredo compartilhado com
outra integração.

## Ativação e rollback futuros

1. Aprovar prazos, frequência, ambiente e responsável pela resposta a alertas.
2. Gerar um `CRON_SECRET` exclusivo no ambiente Preview.
3. Rodar status e dry-run; registrar candidatos e duração.
4. Habilitar uma flag por vez e disparar manualmente no Preview.
5. Verificar tracking, logs, idempotência e impacto no banco.
6. Só então propor o cron em revisão separada; Production requer aprovação nova.

Rollback operacional é configuração: remover/desabilitar a agenda e definir as
flags como `false`. Não faça downgrade para interromper jobs. Se um processo cair,
a lease expira e permite recovery limitado; se falhar repetidamente, o limite de
tentativas fecha o período para investigação.

## Diagnóstico da Lumi

A Lumi está tecnicamente concluída até P6.9 e homologada apenas para uso interno
controlado. Permanecem fora deste gate: ações sobre categorias/budgets/goals,
smoke real multi-turn com OpenAI, medição externa de custo/latência, definição de
testers e rollout público. A sequência recomendada é: medir o uso interno já
autorizado, fechar o gate externo adiado, revisar novas ações em fase própria e,
somente depois, decidir expansão de rollout. `LUMI_PUBLIC_ENABLED`, propostas,
execução e allowlist não foram alteradas por esta consolidação.
