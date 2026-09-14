# Relatório — Open Finance Etapa 2H

## Escopo

A Etapa 2H evolui a correspondência básica entre lançamentos manuais e bancários para uma conciliação determinística, explicável e auditável. Não usa IA, não conecta bancos reais e não altera o ambiente Pluggy Sandbox.

## Algoritmo de correspondência

Um lançamento somente se torna candidato quando pertence ao mesmo usuário, usa a mesma conta Nivra vinculada, tem a mesma direção (`entrada` ou `saida`), o mesmo valor monetário exato e está dentro de uma janela de dois dias antes ou depois do lançamento bancário.

O score interno serve apenas para classificar confiança:

- requisitos econômicos obrigatórios: 75 pontos;
- mesma data: 15 pontos;
- diferença de um dia: 10 pontos;
- diferença de dois dias: 5 pontos;
- descrição normalizada idêntica: 10 pontos;
- sobreposição relevante de palavras: 5 pontos.

Classificação:

- alta: 90 pontos ou mais;
- média: 85 a 89 pontos;
- baixa: abaixo de 85 pontos.

A normalização converte para minúsculas, remove acentos, pontuação, números e termos bancários comuns. A descrição aumenta a confiança, mas sua igualdade não é obrigatória. Transferências internas e pagamentos de cartão identificados pelo mapper do provider permanecem neutros e não entram no matching de receita/despesa.

## Ambiguidade e decisões

Quando uma transação bancária possui mais de um candidato plausível, ou o mesmo lançamento manual aparece para mais de uma transação bancária, o caso é marcado como ambíguo. O sistema não escolhe silenciosamente: a interface mostra cada opção e exige seleção explícita.

As decisões ficam em `correspondencias_conciliacao`, com usuário, transação bancária, transação manual, status, confiança, score, motivos e timestamps. Os estados da decisão são `sugerida`, `confirmada`, `rejeitada` e `reaberta`; o resumo na transação bancária usa `pendente`, `possivel_correspondencia`, `ambigua`, `conciliada`, `ignorada` ou `reaberta`.

Uma rejeição é persistida por par e não volta após uma sincronização comum. Uma mudança econômica no banco — valor, data, direção ou restauração de um registro antes removido — reabre as decisões relacionadas. Alterações apenas descritivas preservam uma confirmação existente.

## Efeito financeiro

Ao confirmar, os registros manual e bancário continuam armazenados. O histórico apresenta uma única linha `Manual + Banco`, o resumo e o dashboard contabilizam o fato econômico uma vez e a categoria escolhida manualmente é preservada. Uma exclusão recebida do provider arquiva a transação bancária em `removida_em`, reabre a conciliação e mantém o lançamento manual visível.

Índices únicos parciais impedem que uma transação bancária ou manual tenha duas correspondências confirmadas. A confirmação bloqueia a linha bancária e valida novamente conta, direção, valor e data antes de gravar a decisão. Todas as rotas usam o usuário da sessão e as escritas exigem CSRF.

## API e interface

Foram adicionadas as operações:

- `GET /api/transactions/reconciliation/suggestions`;
- `POST /api/transactions/reconciliation/confirm-high-confidence`;
- `POST /api/transactions/bank/{bank_id}/reconciliation/{manual_id}/confirm`;
- `POST /api/transactions/bank/{bank_id}/reconciliation/{manual_id}/reject`.

As rotas anteriores de confirmação e rejeição foram mantidas para compatibilidade e só aceitam automaticamente um candidato quando ele é único.

Na página Transações, a revisão usa cards responsivos, mostra a movimentação bancária, as opções manuais, a confiança e motivos em linguagem simples. Casos ambíguos exigem escolha. A confirmação em lote considera somente sugestões únicas e de alta confiança. O histórico ganhou filtro de origem para `Manual`, `Banco` e `Manual + Banco`.

## Migration

A migration `d41e7b9a2c60_advanced_reconciliation.py`:

- adiciona `removida_em` a `transacoes_bancarias`;
- amplia os estados aceitos de conciliação;
- cria `correspondencias_conciliacao` e suas constraints;
- cria unicidade para o par bancária/manual;
- impede mais de uma confirmação para a mesma transação bancária ou manual;
- migra vínculos básicos existentes sem apagar dados.

A migration foi aplicada em banco descartável e o `alembic check` não encontrou diferenças. Após a publicação, o endpoint autenticado de sugestões respondeu normalmente em produção, confirmando que o schema necessário está disponível no Neon.

## Validação executada

- 8 testes específicos de conciliação avançada;
- 22 testes de regressão de sincronização e webhooks;
- 102 testes Python no total, todos aprovados;
- compilação Python aprovada;
- build React/TypeScript aprovado;
- upgrade completo em banco SQLite descartável aprovado;
- `alembic check` aprovado;
- `git diff --check` aprovado;
- revisão local da interface em 375, 390, 430 e 1440 px, sem overflow horizontal;
- temas claro e escuro, seleção por teclado, labels e estado ambíguo validados localmente;
- `/api/health` e `/openapi.json` retornaram HTTP 200 em produção;
- as novas rotas de sugestões e confirmação em lote constam no OpenAPI publicado;
- login, restauração da sessão após refresh e logout foram validados em produção;
- Dashboard e Transações carregaram os dados do Sandbox sem erro;
- produção validada em 375, 390, 430 e 1440 px, nos temas claro e escuro, sem overflow horizontal.

Os testes cobrem match perfeito, incompatibilidades de valor/direção/conta/data, janela temporal, ambiguidade, confirmação, rejeição persistente, idempotência, lote seguro, ownership, CSRF, concorrência, reabertura, remoção externa, histórico/dashboard sem dupla contagem, transferências internas e pagamento de cartão.

## Estado da Etapa 2E

Produção já registrou entregas reais `item/updated` e `transactions/updated` com HTTP 200. `item/login_succeeded` permanece ignorado com segurança por não ser um evento financeiro tratado. A repetição externa do mesmo `eventId` ainda não foi comprovada; por isso a 2E continua com validação externa final pendente.

## Limitações e ativação

O matching usa regras deliberadamente pequenas e conservadoras. Não há aprendizagem automática, conciliação de valor aproximado, divisão de um lançamento em vários ou confirmação automática de casos ambíguos. A conta de produção validada não possuía sugestões pendentes; por isso confirmação, rejeição e ambiguidade foram exercitadas nos testes automatizados e na validação visual local com dados controlados.

Migration, deploy e smoke test de produção foram concluídos. Para encerrar todo o gate Open Finance ainda é necessário executar o roteiro com testers independentes e registrar um retry real do mesmo `eventId` do webhook.

## Próxima tarefa recomendada

Concluir o **Gate final da Prioridade 2 — Open Finance MVP** com as duas evidências externas restantes: roteiro completo por testers independentes e retry idempotente real do mesmo `eventId`. O gate foi executado até o limite das evidências disponíveis e não foi marcado artificialmente como concluído.
