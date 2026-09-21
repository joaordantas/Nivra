# Relatório — Prioridade 5.2: projeção mensal e comprometimento de cartões

## Objetivo

A P5.2 amplia o motor determinístico da Nivra com duas respostas financeiras: como o mês termina considerando somente dados já conhecidos e quanto dos limites dos cartões ativos está comprometido. A entrega mantém o mesmo endpoint autenticado e o mesmo service usado pelo Dashboard e pela ferramenta somente leitura preparada para a futura Lumi.

Não foram implementados modelo de linguagem, chat, ações por IA, notificações, recorrências, orçamentos ou metas.

## Arquitetura

O fluxo continua seguindo:

```text
GET /api/insights
        ↓
InsightService
        ↓
Services financeiros + InsightRepository
        ↓
PostgreSQL
```

O React recebe valores já calculados e apenas os apresenta. A identidade do usuário vem da sessão HTTP-only; `usuario_id` enviado pelo cliente não participa da autorização.

## Definições financeiras

### Realizado

Entradas e despesas econômicas com data menor ou igual à data efetiva da análise. No mês corrente, essa data é o dia atual. São incluídos lançamentos manuais, transações Open Finance de contas vinculadas e compras no cartão.

### Futuro conhecido

Movimentações que já estão persistidas, pertencem ao período solicitado e possuem data posterior à data efetiva. Isso inclui parcelas futuras já criadas pelo parcelamento. A Nivra não presume salário, recorrência ou ritmo de gastos que ainda não esteja registrado.

### Projeção

A projeção é conservadora e reproduzível:

```text
receitas projetadas = receitas realizadas + receitas futuras conhecidas
despesas projetadas = despesas realizadas + despesas futuras conhecidas
resultado projetado = receitas projetadas - despesas projetadas
```

Todos os cálculos financeiros internos usam `Decimal`, com conversão para número apenas no contrato JSON.

## Integridade e dupla contabilização

O motor reutiliza o histórico unificado e o resumo financeiro já existentes. Assim:

- transferências internas permanecem neutras;
- uma conciliação confirmada representa um único evento econômico;
- transações bancárias só entram quando a conta externa está vinculada ao núcleo;
- a compra no cartão é a despesa econômica;
- o pagamento da fatura liquida a obrigação e não cria outra despesa;
- uma parcela futura não entra no realizado antes de sua data;
- movimentações fora do mês solicitado não entram na projeção.

## Comprometimento dos cartões

Somente cartões ativos participam do agregado. Para cada cartão são informados:

- identificação e nome;
- limite total;
- valor comprometido pela regra atual de faturas não pagas;
- limite disponível;
- percentual comprometido;
- valor, fechamento, vencimento e status do ciclo atual;
- valor, vencimento e status da próxima fatura efetivamente pendente.

O resumo agrega limite, comprometimento e disponibilidade dos cartões ativos. Limites iguais ou menores que zero e valores utilizados negativos são tratados de forma segura, sem divisão por zero e sem disponibilidade negativa.

O ciclo atual e a próxima fatura pendente são conceitos separados. Após o fechamento, o ciclo atual pode ser a próxima fatura aberta, enquanto a fatura anterior continua pendente e próxima do vencimento. Os alertas usam a fatura pendente; a apresentação do cartão preserva o ciclo atual.

## Regras de atenção

Os thresholds ficaram centralizados no `InsightService`:

- comprometimento elevado: a partir de 75%;
- comprometimento crítico: a partir de 90%;
- concentração em um cartão: a partir de 70% do total comprometido, quando há mais de um cartão;
- vencimento próximo: até três dias.

Também é emitido alerta quando o resultado realizado ainda é não negativo, mas os compromissos conhecidos deixam a projeção negativa. A priorização existente limita a área “Sua atenção” aos quatro avisos mais relevantes.

## API e contrato

`GET /api/insights` foi ampliado sem remover campos da P5.1. Foram adicionadas as estruturas tipadas:

- `monthly_projection`;
- `card_commitment`;
- detalhes por cartão, incluindo ciclo atual e próxima fatura pendente.

A ferramenta `get_financial_insights` da futura Lumi recebe automaticamente esse contrato pelo service. Ela continua somente leitura, restrita por allowlist, com a identidade injetada pela sessão e sem acesso a repository ou SQL.

## Dashboard

O Dashboard recebeu dois cartões compactos:

- projeção do mês, com resultado realizado, receitas e despesas futuras conhecidas e resultado projetado;
- comprometimento dos cartões, com total utilizado, limite total, percentual, disponibilidade e acesso aos cartões.

Os componentes usam o design system atual, funcionam em tema claro e escuro e passam para uma coluna em telas menores. Há estados próprios de carregamento, ausência de cartões e indisponibilidade. Uma falha em insights continua sem derrubar saldo, resumo ou transações recentes.

O resumo tradicional continua consultando do primeiro dia até hoje. Para a projeção, o Dashboard envia o último dia real do mês (28, 29, 30 ou 31); o backend limita o realizado ao dia atual e usa o restante somente como futuro conhecido.

## Arquivos principais

Criado:

- `tests/test_insight_projection.py`;
- `docs/relatorio-prioridade-5-2-projecao-cartoes.md`.

Alterados:

- `services/insight_service.py`;
- `services/cartao_service.py`;
- `backend/schemas/insights.py`;
- `frontend/src/types.ts`;
- `frontend/src/pages/DashboardPage.tsx`;
- `frontend/src/styles.css`;
- `frontend/src/utils/formatters.ts`;
- `tests/test_open_finance_sync.py`;
- `docs/roadmap.md`;
- `CHANGELOG.md`.

## Banco e migrations

Nenhuma migration foi necessária. Parcelas futuras já são transações persistidas com data própria, e cartões, compras, faturas e pagamentos já fornecem os dados necessários. O head Alembic permanece em `f7b3c1d8e920`.

## Testes

A cobertura específica valida:

- mês vazio, somente receita, somente despesa e resultados positivo/negativo;
- movimentos futuros dentro e fora do mês;
- parcelas futuras;
- transferências neutras;
- compras no cartão e pagamento de fatura sem dupla contabilização;
- fevereiro bissexto e mudança de ano;
- projeção negativa por compromisso futuro;
- cartão sem uso, parcial, próximo do limite e completamente comprometido;
- múltiplos cartões, cartão inativo, limite zero e valores negativos inesperados;
- fatura aberta e paga;
- agregado e alertas;
- transação bancária conciliada contada uma única vez;
- autenticação, falsificação de identidade e isolamento multiusuário;
- allowlist e identidade da ferramenta da futura Lumi.

Resultados finais:

- 131 testes Python aprovados, sem falhas;
- build React/TypeScript aprovado;
- compilação Python aprovada;
- `alembic heads`: `f7b3c1d8e920`;
- `alembic check` aprovado em banco descartável no head, sem operações novas;
- `git diff --check` aprovado;
- busca por credenciais encontrou apenas placeholders em `.env.example` e cenários deliberados de teste;
- validação visual local aprovada em 375 px e 1440 px, nos temas escuro e claro, sem overflow horizontal.

Durante a validação visual foi identificado que o Dashboard usava a data atual também como fim da consulta de insights. Isso escondia compromissos registrados para os dias restantes do mês. O frontend passou a enviar o último dia real do mês para insights, mantendo o resumo realizado limitado a hoje pelo backend. A correção foi confirmada com uma despesa futura: ela permaneceu fora dos gastos realizados e apareceu separadamente na projeção.

## Limitações conhecidas

- a projeção não extrapola ritmo de gastos nem inventa receitas recorrentes;
- recorrências só poderão entrar quando possuírem persistência e regra próprias;
- parcelamentos ainda não são distribuídos automaticamente entre faturas de cartão;
- faturas futuras só são exibidas quando derivadas com segurança das compras existentes;
- orçamentos e metas ainda não alimentam os insights;
- a Lumi ainda não possui modelo de linguagem ou interface de conversa.

## Próxima tarefa recomendada

**P5.3 — Tendências, maiores despesas e contexto consolidado para a Lumi.**

Essa unidade conclui as análises determinísticas centrais ainda pendentes antes de conectar um modelo de linguagem, preservando services como fonte de verdade.
