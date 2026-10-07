# Jobs de resumos periódicos

## Decisão operacional

A Nivra usa FastAPI em funções serverless da Vercel e PostgreSQL/Neon. Instâncias
podem dormir, reiniciar e coexistir, então o processo HTTP não hospeda timer,
thread ou loop de scheduler. A integração preparada é:

```text
Vercel Cron diário
  → GET /api/internal/jobs/periodic-summaries
  → PeriodicSummaryJobRunner
  → PeriodicFinancialSummaryService
  → NotificationService
```

O cron externo decide quando chamar. O runner decide quais períodos e usuários
processar. O serviço P7.5 continua sendo a única fonte das regras financeiras,
preferências, ledger e idempotência da notificação.

Um worker dedicado foi descartado por exigir infraestrutura contínua apenas
para dois jobs. Um scheduler iniciado com o FastAPI foi descartado por não ser
confiável em serverless e poder multiplicar execuções por instância. A CLI
isolada é mantida para operação manual, não como scheduler residente.

## Configuração

| Variável | Comportamento |
| --- | --- |
| `PERIODIC_SUMMARY_JOBS_ENABLED` | Somente `true` habilita execução real; ausente, inválida ou `false` desabilita. |
| `PERIODIC_SUMMARY_BATCH_SIZE` | IDs por lote; padrão 250, faixa de 1 a 1.000. |
| `PERIODIC_SUMMARY_TIMEZONE` | Timezone civil da execução; padrão `America/Sao_Paulo`. |
| `CRON_SECRET` | Segredo exclusivo do trigger, com no mínimo 32 caracteres. |

Nenhum segredo real deve ser versionado. O endpoint usa comparação constante,
não aceita `usuario_id`, query string ou payload e não aparece no schema
OpenAPI. A resposta contém somente tipo, período, status, tentativa, duração e
contadores. O claim persistente limita chamadas simultâneas ao mesmo trabalho,
funcionando como proteção contra repetição do scheduler.

## Frequência e períodos

Uma chamada diária executa semanal e mensal. Para cada tipo, o runner calcula
exclusivamente o período imediatamente anterior e integralmente encerrado:

- semanal: segunda-feira a domingo anteriores à data de referência;
- mensal: primeiro ao último dia do mês anterior.

Chamadas seguintes convergem no tracking já concluído. Se uma chamada for
perdida, ela pode recuperar o período enquanto ele continuar sendo o último
encerrado. O sistema não percorre automaticamente semanas ou meses antigos;
backfill histórico requer decisão e ferramenta futuras.

## Concorrência, falhas e retry

`periodic_summary_job_runs` possui unicidade por tipo e início de período. O
claim transacional grava um token aleatório e lease de quinze minutos. A lease é
renovada por lote; somente o token dono pode finalizar. Se o processo morrer,
outro runner recupera o registro após a expiração. Há no máximo quatro claims
do mesmo job.

Usuários são percorridos por paginação keyset de IDs. Não há transação global do
lote. Falha de um usuário incrementa o contador e o processamento prossegue.
Falhas transitórias de banco, conexão ou timeout recebem até três tentativas por
unidade, com esperas de 250 e 500 ms; erros permanentes não são repetidos. Uma
retomada pode reavaliar usuários já concluídos, mas a chave idempotente de P7.5
impede duplicação.

O tracking termina em `success`, `partial_success` ou `failed` e conserva
contadores de processados, sucessos, suprimidos, sem atividade, falhas e retries.
Somente códigos estáveis de erro são persistidos. Nomes, e-mails, IDs de usuário,
valores, títulos, mensagens e descrições financeiras não são gravados nos logs
do job nem na tabela de execução.

## Execução manual

Dry-run valida referência, período, configuração e contagem de usuários sem
criar notificações, escrever supressões ou alterar tracking:

```powershell
.venv\Scripts\python.exe -m scripts.run_periodic_summary_jobs --dry-run --reference 2026-10-07
```

Execução real exige a feature flag:

```powershell
$env:PERIODIC_SUMMARY_JOBS_ENABLED = "true"
.venv\Scripts\python.exe -m scripts.run_periodic_summary_jobs --kind all --reference 2026-10-07
```

`--kind` aceita `all`, `weekly` ou `monthly`; `--batch-size` permite ajuste
controlado. Código de saída 0 significa conclusão operacional, 1 indica falha ou
limite de tentativas e 2 indica job desabilitado.

## Ativação futura na Vercel

Esta entrega não altera `vercel.json`, não cria cron e não faz deploy. Para uma
ativação futura e revisada:

1. gerar um `CRON_SECRET` exclusivo e configurá-lo apenas no ambiente alvo;
2. configurar `PERIODIC_SUMMARY_JOBS_ENABLED=true`, timezone e batch no ambiente;
3. adicionar ao `vercel.json` um cron diário para
   `/api/internal/jobs/periodic-summaries`, em horário UTC seguro após a virada
   do dia em `America/Sao_Paulo`;
4. revisar o diff e fazer deploy controlado primeiro em Preview;
5. validar autenticação, tracking, logs e idempotência antes de promover;
6. somente então repetir a configuração explicitamente em Production.

O histórico de execuções precisará de política de retenção futura. Nenhuma
limpeza automática foi adicionada nesta fase.
