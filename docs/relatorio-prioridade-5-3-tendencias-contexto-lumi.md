# Relatório — Prioridade 5.3: tendências, maiores despesas e contexto da Lumi

## Objetivo

Ampliar o motor determinístico da Nivra com informações que permitam entender rapidamente a evolução dos gastos, identificar as maiores saídas do período e preparar um contexto seguro para a futura Lumi.

## Implementação concluída

### Maiores despesas

O endpoint `GET /api/insights` agora retorna as cinco maiores despesas do período. Cada item informa descrição, valor, data, categoria, conta, origem e participação percentual no total gasto.

O ranking usa a visão econômica consolidada da Nivra:

- inclui lançamentos manuais;
- inclui movimentações Open Finance de contas vinculadas;
- inclui compras no cartão;
- ignora transferências internas;
- não repete a parte bancária de uma conciliação confirmada;
- mantém o pagamento da fatura fora das despesas econômicas.

### Tendência financeira

Foi criada uma série com seis períodos mensais contendo receitas, despesas e economia.

Quando o mês atual ainda está em andamento, todos os meses são comparados até o mesmo dia. Quando o período termina no último dia do mês, a comparação usa meses completos. Isso evita comparar um mês parcial com um mês inteiro.

O resumo classifica a direção de receitas e despesas como aumento, redução, estável ou dados insuficientes. A faixa de estabilidade é de 5%. Também informa a variação absoluta da economia.

Um alerta adicional é gerado quando os gastos crescem por três períodos equivalentes consecutivos e o aumento acumulado alcança pelo menos 20%. O alerta não é repetido quando a comparação mensal já gerou um aviso equivalente.

### Dashboard

O Dashboard recebeu dois blocos compactos:

- evolução recente dos gastos, com os quatro períodos mais recentes;
- três maiores despesas do período, com categoria e participação no total.

Foram preservados os estados de carregamento, indisponibilidade e ausência de dados. A apresentação se adapta a desktop e mobile e usa as variáveis existentes dos temas claro e escuro.

### Preparação da Lumi

Foi criado um contexto financeiro consolidado contendo:

- posição financeira do período;
- comparação com o período anterior;
- tendência mensal;
- maiores despesas;
- categorias principais;
- projeção mensal;
- comprometimento dos cartões;
- itens de atenção.

O catálogo permitido da Lumi passou a oferecer `get_financial_context`. A ferramenta é somente leitura, recebe o usuário autenticado fora dos argumentos e chama apenas a camada de service. Nenhum modelo de linguagem, chat ou acesso a SQL foi implementado nesta etapa.

O contexto sinaliza explicitamente que orçamentos, metas e recorrências ainda não estão disponíveis, impedindo que integrações futuras tratem dados inexistentes como reais.

## Desempenho

A série de seis meses é obtida em uma leitura consolidada do período e distribuída em memória entre os meses equivalentes. Isso evita repetir seis consultas completas ao banco para montar o gráfico.

## Banco de dados

Nenhuma migration foi necessária. A implementação usa as tabelas e relações já versionadas no head `f7b3c1d8e920`.

## Testes

Foram adicionados cenários para:

- ranking com transações manuais e compras no cartão;
- exclusão de transferências internas;
- isolamento entre usuários;
- participação percentual no total;
- seis meses atravessando a virada do ano;
- fevereiro bissexto;
- comparação até o mesmo dia;
- comparação de meses completos;
- histórico vazio e base zerada;
- crescimento contínuo;
- contexto consolidado da Lumi;
- rejeição de `usuario_id` fornecido nos argumentos da ferramenta.

Validações executadas:

- 135 testes Python: aprovados;
- build React/TypeScript: aprovado;
- compilação Python: aprovada;
- migrations em banco descartável: aprovadas;
- verificação visual responsiva: registrada após a validação final;
- `git diff --check`: executado antes do commit.

## Limitações conscientes

- a tendência considera seis períodos mensais e não tenta prever sazonalidade;
- recorrências ainda não são detectadas;
- orçamentos e metas ainda não existem e permanecem fora do contexto;
- a Lumi ainda não possui modelo de linguagem nem interface de conversa;
- o gráfico é uma leitura resumida, não uma área de análise avançada.

## Próxima tarefa recomendada

**P5.4 — Recorrências determinísticas e refinamento de gastos fora do padrão.**

Essa etapa deve exigir amostra mínima, explicar os critérios usados e permanecer independente de IA. Ela não foi iniciada neste trabalho.
