# Relatório — Prioridade 3.1: Fundação de Parcelamentos

Data da validação: 14 de setembro de 2026.

## Objetivo

A P3.1 criou uma base transacional para compras, despesas e receitas parceladas. O parcelamento passou a existir como uma entidade própria e cada parcela é persistida como uma transação financeira real. A etapa não adicionou recorrências, telas avançadas, projeções ou conversão automática de dados do Open Finance.

## Arquitetura encontrada e preservada

O backend mantém o fluxo `Router → Schema → Service → Repository → Database`:

- os routers autenticam a sessão, exigem CSRF nas escritas e traduzem erros de domínio para HTTP;
- os schemas Pydantic validam o contrato externo;
- os services concentram ownership, validações financeiras, divisão dos valores e calendário;
- os repositories executam consultas e controlam a transação de banco;
- SQLAlchemy Core continua sendo a camada de acesso a PostgreSQL/Neon, com o adaptador SQLite isolado para testes;
- dinheiro continua em `NUMERIC(14, 2)` no banco e usa `Decimal` durante os cálculos;
- datas financeiras continuam como `DATE`, sem conversões de timezone.

As regras existentes para conta ativa, categoria pertencente ao usuário, tipo da movimentação e data foram reutilizadas pelo service de transações.

## Modelagem implementada

Foi criada a tabela `parcelamentos` com:

- `id`;
- `usuario_id`;
- `descricao`;
- `valor_total`;
- `quantidade_parcelas`;
- `data_inicial`;
- `criado_em`;
- `atualizado_em`.

A tabela `transacoes` recebeu campos opcionais:

- `parcelamento_id`;
- `numero_parcela`.

Uma transação comum mantém ambos como `NULL`. O total de parcelas vem do relacionamento com o plano e não é duplicado em cada transação.

## Integridade

O banco e o service garantem, conforme aplicável:

- quantidade mínima de duas parcelas;
- valor total positivo;
- vínculo completo: plano e número ficam ambos preenchidos ou ambos nulos;
- número de parcela positivo;
- unicidade de `(parcelamento_id, numero_parcela)`;
- plano e parcelas pertencentes ao mesmo usuário por foreign key composta;
- validação no service de que os números gerados ficam no intervalo do plano;
- soma persistida exatamente igual ao valor total;
- criação de plano e parcelas em uma única transação;
- rollback completo se qualquer insert falhar;
- exclusão explícita e atômica do grupo, protegida por ownership;
- bloqueio de edição e exclusão isolada de parcelas.

Correspondências Open Finance ligadas a uma parcela são liberadas antes da exclusão do grupo, evitando referências quebradas. A detecção de conciliação existente continua sendo acionada após criação ou exclusão.

## Divisão monetária

O valor é quantizado em centavos com `Decimal` e `ROUND_HALF_UP`, convertido para centavos inteiros e dividido com `divmod`. O restante é distribuído, de forma estável, a partir da primeira parcela.

Exemplo para R$ 100,00 em três parcelas:

1. R$ 33,34;
2. R$ 33,33;
3. R$ 33,33.

Valores menores que um centavo por parcela são rejeitados porque gerariam parcelas de valor zero.

## Política de datas

Todas as datas usam o dia original da primeira parcela como âncora. Quando esse dia não existe no mês de destino, a parcela usa o último dia válido daquele mês. A parcela seguinte volta a tentar o dia original.

Assim, uma sequência iniciada em 31 de janeiro pode resultar em 28 ou 29 de fevereiro e volta a 31 de março. Foram cobertos fevereiro comum, ano bissexto, meses de 30 dias e virada de ano.

## API mínima

Foram adicionadas rotas autenticadas em `/api/installment-plans`:

- `POST /api/installment-plans` — cria o plano e todas as parcelas;
- `GET /api/installment-plans` — lista somente os planos do usuário atual;
- `GET /api/installment-plans/{id}` — retorna o plano e suas parcelas;
- `DELETE /api/installment-plans/{id}` — exclui o grupo completo.

Criação e exclusão exigem token CSRF. O identificador do usuário vem exclusivamente da sessão do backend.

## Migration

- revision: `f7b3c1d8e920`;
- revisão anterior: `d41e7b9a2c60`;
- novo head: `f7b3c1d8e920`.

A migration cria a nova tabela, adiciona as duas colunas opcionais em `transacoes`, cria foreign keys, checks, unique constraints e índices. O upgrade preservou uma transação preexistente com os novos campos nulos. O downgrade removeu apenas a estrutura da P3.1 e preservou a transação antiga.

O importador SQLite legado passou a descobrir dinamicamente o head do Alembic. A verificação de órfãos também passou a ignorar uma relação composta quando a estrutura completa dessa relação ainda não existe no SQLite legado, sem permitir que relações antigas válidas sejam ignoradas.

## Testes executados

- suíte Python completa: 114 testes aprovados, 0 falhas;
- testes novos da P3.1: 12 métodos aprovados;
- testes do importador SQLite: 5 aprovados;
- migration descartável: upgrade da revisão anterior ao head aprovado;
- preservação de dados existentes no upgrade: aprovada;
- downgrade para `d41e7b9a2c60`: aprovado;
- retorno ao head: aprovado;
- `alembic current`: `f7b3c1d8e920 (head)` no banco descartável;
- `alembic check`: nenhuma operação nova detectada.

Os testes novos cobrem 2x, 3x, 12x, divisão com centavos, valores pequenos, calendário, ownership, numeração, soma exata, rollback, exclusão sem órfãos, bloqueio de mutação isolada, compatibilidade de transações normais e API com sessão/CSRF.

## Compatibilidade

A suíte existente confirma que autenticação, contas, categorias, dashboard, cartões/faturas, Open Finance, webhooks, conciliação e transações manuais continuam funcionando. Não houve alteração visual no frontend nesta etapa.

## Riscos e pendências para P3.2

- ainda não existe fluxo visual para criar, listar ou excluir parcelamentos;
- integração de parcelamentos com cartões, faturas e limite permanece pendente;
- parcelas futuras seguem a semântica atual de transações do núcleo; projeções e o efeito temporal no saldo devem ser definidos antes da UX final;
- não existe edição do grupo; as parcelas ficam protegidas contra edição isolada;
- recorrências não foram iniciadas;
- a migration precisa ser aplicada manualmente no Neon antes de publicar código que use as novas rotas.

## Resultado

**GATE P3.1: APROVADO**
