# Relatório — Open Finance 2D.5: vínculo de contas e saldo bancário

Data: 13 de setembro de 2026  
Status: implementado e validado localmente; ativação no Neon/Vercel pendente

## Escopo concluído

Esta atualização conclui a primeira unidade lógica da Etapa 2D.5. Uma conta bancária externa sincronizada pode ser vinculada a uma conta Nivra existente ou originar uma nova conta Nivra. Depois do vínculo, o saldo informado pelo provider passa a ser o saldo atual apresentado pela Nivra.

O histórico principal, as receitas e despesas externas, a categorização bancária e a conciliação ainda não fazem parte desta entrega.

## Modelagem e migration

A relação já existente `contas_bancarias_externas.conta_nivra_id` continua sendo a única fonte do vínculo. Não foi criada uma segunda tabela nem um campo de origem duplicado.

A migration `f4a7c2d9e510` adiciona a constraint única `uq_contas_externas_conta_nivra`. Ela garante que uma conta Nivra não possa ser vinculada simultaneamente a duas contas externas. Como o campo é anulável, contas externas ainda não vinculadas continuam válidas.

O vínculo usa bloqueio de linha no PostgreSQL e a criação de conta mais vínculo ocorre em uma única transação. Se qualquer parte falhar, toda a operação sofre rollback.

## Regras aplicadas

- apenas contas externas do tipo bancário (`BANK`) e em BRL podem ser vinculadas ao núcleo de contas;
- cartões externos não são convertidos em contas financeiras;
- a conta Nivra de destino deve pertencer ao usuário autenticado e estar ativa;
- outra conta externa não pode ocupar a mesma conta Nivra;
- o usuário pode trocar o vínculo para outra conta própria disponível;
- uma conta criada a partir do banco recebe saldo inicial zero e usa o saldo sincronizado como saldo atual;
- contas manuais continuam calculando saldo inicial mais movimentações manuais;
- quando o provider não informa saldo, a conta vinculada mantém o cálculo manual como fallback;
- a sincronização atualiza o saldo externo sem remover o vínculo.

## API

Foram adicionadas duas operações protegidas por sessão e CSRF:

- `PATCH /api/open-finance/external-accounts/{id}/link`: vincula a uma conta Nivra existente;
- `POST /api/open-finance/external-accounts/{id}/nivra-account`: cria e vincula uma conta Nivra na mesma transação.

A listagem de contas externas agora informa o vínculo atual e se aquela conta pode ser vinculada. A listagem comum de contas informa origem, instituição, conta externa e horário da última sincronização.

## Interface

Na seção Open Finance da página Contas, cada conta bancária sincronizada permite:

- escolher uma conta Nivra disponível;
- salvar ou alterar o vínculo;
- criar uma nova conta Nivra;
- visualizar qual conta já está vinculada.

As contas vinculadas recebem o indicador discreto `Banco`, exibem a instituição e a última sincronização. A edição visual do saldo inicial fica desabilitada porque o saldo atual vem do provider. Cartões sincronizados mostram que sua integração ocorrerá na área própria de cartões.

## Efeito no dashboard

O dashboard já soma a resposta de `/api/accounts`. Por isso, o saldo de uma conta bancária vinculada entra automaticamente no saldo consolidado uma única vez. Uma conta Nivra sem vínculo continua usando o saldo manual.

Entradas, gastos, economia e movimentações recentes continuam baseados em `transacoes`. As transações de `transacoes_bancarias` ainda não entram nesses valores.

## Validações realizadas

- compilação dos módulos Python: aprovada;
- testes específicos de persistência e sincronização Open Finance: 15 aprovados;
- suíte Python completa: 80 testes aprovados;
- frontend React/TypeScript: build aprovado;
- upgrade completo em banco descartável até `f4a7c2d9e510`: aprovado;
- `alembic current`: `f4a7c2d9e510 (head)` no banco descartável;
- `alembic check`: nenhuma nova operação de upgrade detectada;
- verificação de isolamento: usuário B não acessa nem vincula conta externa do usuário A;
- verificação de CSRF: operação sem token é recusada;
- verificação de idempotência e conflito: o mesmo destino não pode ser usado por duas contas externas;
- re-sync: atualiza o saldo e preserva o vínculo.

## Ativação manual no Neon e na Vercel

Antes de publicar o código, aplicar a migration no Neon principal usando a conexão sem pool já configurada:

```powershell
alembic upgrade head
alembic current
```

O resultado esperado de `alembic current` é:

```text
f4a7c2d9e510 (head)
```

Depois disso, o commit pode ser enviado ao GitHub para disparar o deploy na Vercel. Nenhuma credencial deve ser incluída nos comandos registrados, na documentação ou no repositório.

## Verificação recomendada em produção

1. entrar com uma conta de teste;
2. sincronizar a conexão Sandbox;
3. vincular a conta corrente externa a uma conta Nivra existente;
4. confirmar o indicador `Banco`, o saldo e a última sincronização;
5. conferir que o saldo consolidado e o saldo do dashboard incluem o valor uma única vez;
6. trocar o vínculo para outra conta própria e confirmar que a anterior volta ao cálculo manual;
7. executar nova sincronização e confirmar que saldo e horário mudam sem perder o vínculo;
8. confirmar que o cartão externo não oferece criação de conta financeira.

## Limitações conhecidas

- o histórico principal ainda não exibe transações bancárias;
- os totais de entradas e gastos ainda usam somente transações manuais;
- transações manuais ainda podem ser cadastradas em uma conta vinculada, mas não alteram o saldo bancário exibido;
- a conciliação entre lançamentos manuais e bancários ainda não foi implementada;
- a migration ainda precisa ser aplicada no Neon principal antes do deploy desta versão.

## Próxima tarefa recomendada

**Etapa 2D.5 — histórico unificado de transações manuais e bancárias.**

Essa unidade deve preservar busca, filtros, ordenação e isolamento, indicar a origem `Manual` ou `Banco`, resolver categorias pela chave estável e preparar a conciliação básica. A Etapa 2E — Webhooks permanece posterior à conclusão da integração visível com o núcleo.
