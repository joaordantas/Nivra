# Relatório — Open Finance 2E: webhooks

Data: 13 de setembro de 2026
Status: implementada e publicada; validação externa final pendente

## Entrega

A Nivra recebeu um endpoint server-to-server para webhooks Pluggy:

`POST /api/open-finance/webhooks/pluggy`

O endpoint não usa sessão de usuário nem CSRF. A autenticidade é validada por um segredo de pelo menos 32 caracteres enviado no header `X-Nivra-Webhook-Secret` e comparado em tempo constante.

## Eventos

Eventos suportados:

- `item/updated`: executa uma sincronização completa do Item;
- `item/error`: registra o erro e atualiza o estado da conexão;
- `item/deleted`: marca a conexão como desconectada;
- `transactions/created`: busca e inclui somente o lote criado;
- `transactions/updated`: consulta por IDs e atualiza os registros indicados;
- `transactions/deleted`: remove somente os IDs indicados.

Eventos válidos de outros tópicos e Items ainda desconhecidos são confirmados como ignorados, evitando retentativas sem utilidade.

## Idempotência e retry

A tabela `eventos_webhook_open_finance` registra:

- provider e `eventId`;
- tipo e Item;
- conexão associada;
- hash canônico do conteúdo conhecido;
- estado, tentativas e quantidade processada;
- erro seguro e timestamps.

A constraint `uq_eventos_webhook_provider_evento` permite uma única entrada por evento. Uma reivindicação atômica impede duas entregas simultâneas de processarem o mesmo evento. Processamentos interrompidos podem ser retomados depois de cinco minutos. Uma repetição já concluída recebe HTTP 200 sem executar novamente. Se o mesmo identificador chegar com conteúdo diferente, a Nivra devolve HTTP 409. Falhas temporárias ficam registradas e recebem HTTP 503, permitindo nova tentativa com o mesmo `eventId`.

## Segurança e logs

- segredo ausente no servidor: HTTP 503;
- segredo ausente ou incorreto na chamada: HTTP 401;
- payload permanentemente inválido: HTTP 400/409/422;
- falha temporária do provider ou processamento: HTTP 503;
- sucesso, duplicação ou evento ignorado: HTTP 200.

Os logs da aplicação contêm tipo, identificador do evento, estado e quantidade processada. Payload financeiro, segredo e credenciais não são registrados.

## Migration

`a93c7e4d5f21 — open finance webhook inbox`

Ela cria a caixa de entrada persistente, constraint de unicidade, checks de estado/tentativas/quantidade e índice por Item/data.

## Validação local

- 94 testes Python aprovados;
- 10 testes específicos de webhook aprovados;
- criação, atualização, exclusão, duplicação, retry e conflito de payload cobertos;
- concorrência simulada e recuperação de processamento interrompido cobertas;
- conciliação reaberta quando valor, data ou direção bancária muda;
- migration aplicada do zero em banco descartável até `a93c7e4d5f21 (head)`;
- `alembic check` sem operações pendentes;
- compilação Python aprovada;
- build React/TypeScript aprovado.

A migration foi aplicada no Neon principal como `a93c7e4d5f21 (head)`. O endpoint está publicado na Vercel, as variáveis de webhook foram configuradas e o script de registro confirmou a atualização segura do webhook na Application Sandbox.

A validação externa final permanece pendente: a Pluggy ainda precisa entregar um evento real e a mesma entrega deve ser repetida para confirmar a idempotência ponta a ponta. O provider limitou uma nova atualização do Item Sandbox por frequência; isso não indica falha na Nivra.

## Ativação manual

1. aguardar a janela permitida pelo Sandbox e solicitar nova atualização do Item;
2. confirmar a entrega no painel Events da Pluggy;
3. confirmar resposta HTTP 2xx e o registro em `eventos_webhook_open_finance`;
4. repetir o mesmo evento e verificar que não há processamento ou dado duplicado.

## Limitação operacional

O processamento ocorre dentro da requisição do FastAPI. As consultas de transações são direcionadas para reduzir duração; `item/updated` continua executando o snapshot completo. A persistência por `eventId` torna uma retentativa segura caso a função ou o provider falhe. Uma fila externa não foi adicionada nesta etapa.

## Próxima tarefa

A Etapa 2F — UX Open Finance foi concluída separadamente. A validação externa real dos webhooks continua pendente e não bloqueia a próxima unidade de produto, a **Etapa 2G — Demo para testers**.
