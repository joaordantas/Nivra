# Relatório — Prioridade 5.1: insights determinísticos iniciais

## Objetivo

Iniciar as Prioridades 5 e 6 por uma unidade pequena e segura: transformar a área “Sua atenção” em uma análise produzida pelo backend e preparar um contrato controlado que a futura Lumi poderá usar. Esta entrega não conecta um modelo de linguagem e não implementa chat.

## Motor financeiro

Foi criado um serviço determinístico que recebe o usuário autenticado e um período. Ele produz:

- resumo de entradas, gastos e economia;
- comparação com o período anterior equivalente;
- categorias com maior volume de despesas e receitas;
- detecção inicial de gastos fora do padrão;
- avisos priorizados para a área “Sua atenção”.

No mês corrente, a análise termina no dia atual. Assim, setembro até o dia 20 é comparado com agosto até o dia 20, evitando comparar um mês parcial com um mês completo.

As regras atuais podem avisar sobre:

- gastos maiores que as entradas;
- crescimento de gastos de pelo menos 20% sobre o período anterior;
- uma despesa pelo menos duas vezes maior que a mediana, com valor mínimo de R$ 100 e ao menos três despesas na amostra;
- categoria concentrando ao menos 40% das despesas, quando há amostra suficiente;
- economia positiva no período;
- ausência de movimentações.

As regras são transparentes, reproduzíveis e não dependem de IA.

## Integridade financeira

O motor reutiliza o resumo financeiro e o histórico unificado existentes. Com isso:

- transações manuais e Open Finance vinculadas são consideradas;
- conciliações confirmadas permanecem como um único evento econômico;
- transferências internas continuam neutras;
- compras no cartão entram como despesa econômica;
- o pagamento da fatura não vira uma segunda despesa;
- compras futuras e transações futuras não entram antes da data apropriada.

## API

Foi adicionado `GET /api/insights`, protegido pela sessão server-side. O frontend informa somente as datas. A identidade é obtida pelo backend e os dados de outro usuário não podem ser solicitados por parâmetro.

A resposta é tipada e contém período atual/anterior, resumos, comparações, categorias, despesas incomuns e avisos.

## Dashboard

O bloco “Sua atenção” deixou de decidir o estado financeiro dentro do React. Agora ele apresenta os avisos retornados pelo backend com quatro níveis visuais:

- informação;
- positivo;
- atenção;
- risco.

Uma falha exclusiva no endpoint de insights não derruba saldo, cartões de resumo, contas ou transações recentes. O Dashboard informa a indisponibilidade da análise e mantém os demais dados utilizáveis.

## Preparação da Lumi

Foi criado um catálogo inicial de ferramentas permitido por lista explícita. A primeira ferramenta é somente leitura e consulta o mesmo serviço de insights usado pelo Dashboard.

O executor:

- aceita apenas ferramentas cadastradas;
- injeta o `usuario_id` da sessão;
- ignora qualquer tentativa de fornecer outra identidade nos argumentos;
- chama services existentes;
- não oferece SQL nem repositories à futura IA.

Essa estrutura prepara tool calling sem criar uma integração prematura com um provedor de modelo. Lumi, chat, linguagem natural e ações financeiras continuam pendentes.

## Arquivos principais

Criados:

- `repositories/insight_repo.py`;
- `services/insight_service.py`;
- `services/lumi_tool_service.py`;
- `backend/schemas/insights.py`;
- `backend/routers/insights.py`;
- `tests/test_insights.py`.

Alterados:

- `backend/main.py`;
- `frontend/src/services/api.ts`;
- `frontend/src/types.ts`;
- `frontend/src/pages/DashboardPage.tsx`;
- `frontend/src/styles.css`;
- `docs/roadmap.md`;
- `CHANGELOG.md`.

## Banco e migrations

Nenhuma tabela, constraint ou migration foi criada. A entrega consulta as estruturas financeiras existentes e mantém o head Alembic em `f7b3c1d8e920`.

## Validação

- 4 testes específicos de insights: aprovados;
- suíte Python completa: 122 testes aprovados, 0 falhas;
- build React/TypeScript: aprovado;
- compilação Python: aprovada;
- head Alembic identificado: `f7b3c1d8e920`.

O `alembic check` sem uma `DATABASE_URL` local configurada recusou a conexão como previsto pela proteção do projeto. Não há alteração de schema nesta entrega.

## Limitações atuais

- a detecção de gasto incomum usa uma regra estatística inicial, ainda sem histórico longo por estabelecimento ou categoria;
- recorrências, tendência de vários meses, projeção, cartões futuros, orçamentos e metas ainda não alimentam os insights;
- a Lumi ainda não possui modelo, chat ou tool calling externo;
- os alertas aparecem dentro do Dashboard; notificações persistentes e WhatsApp pertencem às etapas posteriores.

## Próxima tarefa recomendada

**P5.2 — Projeção mensal e comprometimento de cartões.**

Essa unidade deve ampliar o contexto determinístico que a Lumi consumirá, incluindo faturas e compromissos futuros, antes da conexão com um modelo de linguagem.
