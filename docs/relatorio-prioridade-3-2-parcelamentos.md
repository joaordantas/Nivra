# Relatório — Prioridade 3.2: UX e Integração de Parcelamentos

Data da validação: 14 de setembro de 2026.

## Objetivo

A P3.2 tornou utilizável a fundação de parcelamentos entregue na P3.1. O usuário pode criar uma receita ou despesa parcelada no formulário normal de movimentações, acompanhar o grupo, abrir suas parcelas e alterar ou excluir o plano com regras que preservam a integridade financeira.

Recorrências, alterações estruturais e integração de parcelamentos com cartões e faturas não fazem parte desta etapa.

## Experiência implementada

O formulário de movimentações ganhou a escolha `À vista` ou `Parcelado` para receitas e despesas. A opção parcelada pede somente a quantidade e usa a data da movimentação como data da primeira parcela. Transferências continuam fora desse fluxo.

Antes de salvar, a interface mostra quantidade e valor mensal quando a divisão é exata. Quando há centavos residuais, informa o total e deixa claro que o backend fará a distribuição. A regra definitiva continua no service, com `Decimal` e soma exata.

No histórico, cada parcela mantém a descrição original e recebe um indicador separado `X/Y`. Parcelas futuras também exibem o estado `Futura`. O indicador abre o detalhe do grupo.

## Lista, detalhe e progresso

A página de Transações possui um painel compacto de parcelamentos. Cada plano apresenta:

- descrição e valor total;
- quantidade de parcelas;
- progresso por data;
- próxima data relevante;
- acesso ao detalhe completo.

O detalhe apresenta a primeira e a última parcela, valor e data de cada item, categoria, conta e posição `X/Y`. O texto da interface explica que “Data atingida” indica apenas posição no calendário e não confirma pagamento.

## Edição e exclusão

Foi adicionado `PATCH /api/installment-plans/{id}`. Nesta versão, apenas campos não estruturais podem ser alterados:

- descrição;
- categoria;
- conta.

A alteração é propagada para todas as parcelas em uma única transação de banco. O valor total, a quantidade e a data inicial permanecem imutáveis, evitando recriação ingênua de parcelas já ocorridas. Se alguma parcela possuía conciliação bancária, a decisão é reaberta para nova análise porque categoria, conta ou descrição podem alterar a correspondência.

A exclusão usa a operação atômica da P3.1 e exige confirmação explícita de que todas as parcelas serão removidas. Não existe ação de editar ou excluir uma parcela isolada.

## Regra temporal e saldo atual

Parcelas são transações reais e continuam visíveis cronologicamente, inclusive quando futuras. Para os números atuais, foi adotada esta regra:

- uma parcela com data igual ou anterior ao dia atual participa do saldo e do resumo financeiro;
- uma parcela com data futura permanece como projeção e não altera saldo, entradas, gastos ou economia;
- o histórico não esconde parcelas futuras.

Essa regra evita retirar o valor total de uma conta bancária na criação do plano e também evita fingir que uma parcela futura já ocorreu.

## Cartões e faturas

O fluxo existente de cartões registra compras em `compras_cartao` e distribui o efeito financeiro por faturas. A fundação da P3.1 representa parcelas como `transacoes` do núcleo. Unir os dois modelos nesta etapa criaria risco de dupla despesa, limite incorreto e distribuição errada entre faturas.

Por isso, a P3.2 preserva o comportamento atual de cartões e faturas. A integração completa será uma unidade própria, com distribuição entre ciclos, comprometimento de limite e projeção de faturas futuras.

## Backend e contratos

O retorno do parcelamento passou a incluir primeira data, última data, quantidade de datas atingidas, quantidade futura e próxima data. Cada parcela informa somente um `status_temporal`: `data_atingida` ou `futura`.

O contrato não expõe um campo “paga”, porque a aplicação ainda não possui confirmação de liquidação por parcela. Frontend e backend possuem tipos explícitos e não utilizam `any` nesse fluxo.

## Estados e responsividade

Foram implementados estados de carregamento, vazio, erro e sucesso para a lista e o detalhe. Criação, edição e exclusão desabilitam a ação durante o processamento, reduzindo o risco de envio repetido. O modal e as listas se reorganizam para telas pequenas, sem depender de hover para abrir ou administrar o grupo.

## Testes executados

- testes direcionados de parcelamentos, contas, dashboard e cartões/faturas: 37 aprovados;
- suíte Python completa: 118 testes aprovados, 0 falhas;
- testes da fundação e UX de parcelamentos: 16 métodos aprovados;
- build React/TypeScript: aprovado;
- compilação Python: aprovada;
- migration descartável e Alembic: mesmo head `f7b3c1d8e920`, sem nova migration na P3.2;
- verificação visual responsiva em 375, 390, 430, 612 e 1440 px: aprovada nos temas claro e escuro, sem overflow horizontal;
- fluxo visual local: criação, preview desigual, histórico `X/Y`, progresso temporal, detalhe, edição do grupo e fechamento por `Esc` aprovados;
- console do navegador durante a validação final: sem erros ou avisos.

Os testes novos cobrem progresso temporal sem inventar pagamento, propagação segura de campos no grupo, ownership do `PATCH`, presença das parcelas futuras no histórico, exclusão delas dos totais atuais e reconhecimento gradual de parcelas cuja data já chegou.

## Arquivos principais da P3.2

- `backend/routers/installments.py`;
- `backend/schemas/installments.py`;
- `repositories/parcelamento_repo.py`;
- `repositories/conta_repo.py`;
- `services/parcelamento_service.py`;
- `services/transacao_service.py`;
- `frontend/src/components/finance/MovementForm.tsx`;
- `frontend/src/components/finance/InstallmentPlans.tsx`;
- `frontend/src/pages/TransactionsPage.tsx`;
- `frontend/src/pages/DashboardPage.tsx`;
- `frontend/src/services/api.ts`;
- `frontend/src/types.ts`;
- `frontend/src/styles.css`;
- `tests/test_installments.py`.

## Limitações e pendência operacional

- alterações de valor total, quantidade e data inicial permanecem bloqueadas;
- parcelamentos em cartões e projeção de faturas permanecem pendentes;
- não existe status de pagamento individual;
- recorrências não foram iniciadas;
- a migration `f7b3c1d8e920` precisa estar aplicada no Neon antes do deploy do conjunto P3.1/P3.2. As credenciais do Neon não estavam disponíveis neste ambiente, então nenhuma alteração foi feita no banco de produção.

## Resultado

**GATE P3.2: APROVADO**, condicionado operacionalmente à aplicação da migration P3.1 no Neon antes da publicação.

## Próxima tarefa recomendada

**P3.3 — Integração de parcelamentos com cartões e faturas**, incluindo distribuição entre ciclos, comprometimento do limite e projeção de faturas futuras.
