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

Somente notificações **lidas**, cujo `lida_em` seja anterior ao cutoff, são
removidas. Assim, uma notificação antiga lida recentemente recebe a janela
completa aprovada. Notificações não lidas não expiram. A manutenção não lê nem
altera contas, transações,
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

## Política de retenção aprovada para o piloto

Os prazos abaixo foram aprovados pelo responsável em 10 de outubro de 2026 para
uso controlado no Preview. A aprovação define a política, mas não agenda nem
executa limpeza: a feature flag continua fail-closed, não existe Cron ativo e
Production permanece inalterada.

| Categoria | Finalidade | Recomendação proposta | Alternativas | Impacto e risco de exclusão | Risco de retenção excessiva |
| --- | --- | --- | --- | --- | --- |
| Notificações lidas | histórico recente e suporte ao usuário | 180 dias após `lida_em` | 90 dias para maior minimização; 365 dias para histórico longo | perda do histórico visual após o prazo; dedupe permanece | crescimento do feed e conservação desnecessária de texto financeiro |
| Notificações não lidas | garantir ciência do evento | sem expiração automática no mecanismo atual | futura política de arquivamento com aviso, em fase própria | exclusão prematura pode ocultar alerta ainda não visto | crescimento indefinido; exige acompanhamento de volume |
| Histórico de jobs | diagnóstico, tendência e auditoria operacional | 180 dias após conclusão, preservando sempre o último por tipo | 90 ou 365 dias | janela menor reduz investigação histórica | metadados são pequenos, mas crescimento indefinido não tem finalidade |
| Logs sanitizados da plataforma | resposta a incidentes | 30 dias | 14 ou 90 dias conforme capacidade e requisito jurídico | janela curta pode impedir correlação tardia | custo e exposição operacional desnecessários, mesmo sem payload financeiro |
| Ledger de deduplicação | impedir reaparecimento de eventos antigos | vida da conta, apagado em cascata com o usuário | TTL somente após redesenho dos produtores | remover permite recriação de alertas antigos | crescimento por evento; contém apenas usuário, chave técnica e instante |
| Estados de alertas financeiros | progressão monotônica de marcos | vida da conta/fonte; revisão separada para fontes excluídas | limpeza após prova de inexistência da fonte e janela aprovada | remover pode repetir marcos de orçamento/meta | estados órfãos podem se acumular |
| Preferências | respeitar escolha vigente do usuário | vida da conta | nenhuma alternativa automática recomendada | exclusão reativa defaults e pode mudar consentimento prático | baixo volume; risco principal é governança, não armazenamento |

A política aprovada é: notificações lidas por 180 dias após `lida_em`, histórico
terminal de jobs por 180 dias preservando sempre o último por tipo, logs
sanitizados por 30 dias e notificações não lidas sem expiração automática. A
avaliação jurídica/LGPD do texto apresentado ao usuário continua necessária
antes de abertura pública. Qualquer mudança exige atualizar este runbook; ledger,
preferências, estados financeiros e proteção de não lidas não podem ser
alterados sem fase própria.

## Evidência ambiental de 8 de outubro de 2026

| Superfície | Evidência | Conclusão |
| --- | --- | --- |
| Local | commit `bf8b10c`, árvore inicialmente limpa, head Alembic `f5a6b7c8d9e0` | implementação atual disponível |
| GitHub | `main` em `2aab7b4`; `bf8b10c` não publicado; branch local sem equivalente remoto | não há origem remota para um Preview atual |
| Último Preview registrado | deployment bem-sucedido no commit `e2d968a`, ancestral e dez commits atrás do gate local | código P7/P8/P9 ausente |
| Banco Preview base | revision `b5c7d9e1f203`, sem ledger/colunas novas | não compatível com este gate |
| Banco Preview branch | revision `d7e8f9a012b3`, sem ledger/colunas novas | não compatível com este gate |
| Acesso HTTP do Preview | URL responde com login da Vercel antes da API | health, OpenAPI e flags não puderam ser observados externamente |
| Production | health público online no deployment `2aab7b4`; fingerprint de banco distinto dos candidatos Preview | permaneceu somente leitura e inalterada |

Nenhum status ou dry-run foi executado contra Preview porque código e schema não
estão alinhados. As duas operações foram aprovadas apenas localmente e no banco
PostgreSQL descartável.

## Checklist de prontidão para Preview

- [x] Código local e migration aprovados em regressão.
- [x] Banco descartável separado de Preview e Production validado e removido.
- [x] Endpoints internos, flags e segredo possuem testes fail-closed.
- [x] Proposta de retenção documentada sem ativação.
- [x] Candidatos de banco Preview distinguíveis do fingerprint de Production.
- [ ] Aprovação humana dos prazos de retenção.
- [ ] Autorização explícita para push e criação de deployment Preview.
- [ ] Branch remota contendo `bf8b10c` ou sucessor revisado.
- [ ] Confirmação, na Vercel, do vínculo exato entre deployment e banco Preview.
- [ ] Snapshot/restore point do banco Preview e migration até `f5a6b7c8d9e0`.
- [ ] `CRON_SECRET` exclusivo no escopo Preview, sem reutilização de Production.
- [ ] Todas as flags de jobs e manutenção confirmadas como `false` após deploy.
- [ ] `status` e `cleanup --dry-run` executados no Preview atualizado.
- [ ] Logs e métricas observados no runtime real sem PII.
- [ ] Aprovação separada antes de qualquer execução real ou Cron.

## Implantação futura autorizada

1. Publicar o commit aprovado em branch de revisão; não usar `main`.
2. Criar deployment Preview e comprovar o SHA pelo registro da plataforma.
3. Vincular somente o projeto/branch Neon de Preview e comparar seu fingerprint
   com Production antes de qualquer migration.
4. Criar snapshot/restore point e aplicar `upgrade` seguido de `alembic check`
   somente no banco Preview autorizado.
5. Manter `PERIODIC_SUMMARY_JOBS_ENABLED`, `FINANCIAL_ALERTS_ENABLED` e
   `NOTIFICATION_MAINTENANCE_ENABLED` em `false`.
6. Configurar um `CRON_SECRET` exclusivo de Preview, mas não configurar agenda.
7. Executar health, OpenAPI, CLI `status` e dry-run; confirmar logs sanitizados.
8. Registrar os resultados antes de pedir autorização para qualquer job real.

Rollback de código usa o deployment Preview anterior. Rollback operacional
mantém ou restaura as três flags para `false` e remove qualquer agenda. Migration
não deve ser revertida como mecanismo de desligamento; se uma migration falhar,
interromper o gate e restaurar o banco Preview pelo procedimento aprovado.

Uma futura ativação de Cron exige: deployment/schema alinhados, segredo exclusivo,
flags aprovadas individualmente, responsável por alertas, frequência e timezone
documentados, dry-run aprovado, plano de rollback testado e nova autorização
explícita. Nada disso foi ativado neste gate.
