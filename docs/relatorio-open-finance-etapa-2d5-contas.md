# Relatório — Open Finance 2D.5: integração com o núcleo

Data: 13 de setembro de 2026  
Status: concluída e validada localmente; migration final e deploy pendentes

## Escopo concluído

A Etapa 2D.5 integra ao núcleo da Nivra os dados bancários que as Etapas 2C e 2D já sincronizam. Contas externas podem criar ou ser vinculadas a contas Nivra, o saldo informado pelo provider passa a ser a fonte do saldo atual e as transações bancárias vinculadas aparecem no histórico e nos totais financeiros.

Os registros externos continuam em `contas_bancarias_externas` e `transacoes_bancarias`. A consulta combina dados manuais e bancários sem copiar transações para `transacoes`.

## Vínculo de contas e saldo

- contas externas `BANK` em BRL podem criar ou vincular uma conta Nivra;
- cartões externos permanecem fora do núcleo de contas e aguardam integração própria;
- uma conta Nivra não pode ser vinculada a duas contas externas;
- criação da conta e vínculo são atômicos;
- o vínculo só pode usar recursos do usuário autenticado;
- o saldo sincronizado é a fonte do saldo atual da conta vinculada;
- contas sem vínculo preservam o cálculo manual;
- origem, instituição e horário da última sincronização aparecem na interface.

## Histórico unificado

A listagem principal reúne:

- lançamentos de `transacoes`;
- transações bancárias de contas externas vinculadas;
- origem `Manual`, `Banco` ou `Manual + Banco`;
- categoria resolvida pela `chave_sistema` da categoria padrão pertencente ao usuário;
- fallback `other` para categorias externas desconhecidas;
- busca, filtros, ordenação e isolamento por usuário.

Transações bancárias são somente leitura na Nivra. Editar ou excluir uma transação manual conciliada desfaz a associação para impedir uma deduplicação incorreta.

## Conciliação básica

O detector determinístico considera:

- a mesma conta Nivra vinculada;
- a mesma direção financeira;
- o mesmo valor monetário com duas casas decimais;
- diferença máxima de dois dias;
- correspondência única e sem ambiguidade.

Um candidato permanece contado e visível até o usuário confirmar. Na confirmação, os dois registros originais são preservados, o histórico exibe um único lançamento como `Manual + Banco` e os totais deixam de contar a duplicação. Na rejeição, os registros continuam separados e a decisão sobrevive a novas sincronizações.

A constraint `uq_transacoes_bancarias_transacao_nivra` impede que a mesma transação manual seja conciliada com mais de uma transação bancária.

## Transferências e cartão

- transferências manuais permanecem neutras;
- pares bancários entre contas próprias, com valor oposto e datas próximas, são tratados como transferência interna neutra;
- categorias bancárias de transferência para a mesma pessoa também são neutras;
- pagamentos de cartão são neutros para não registrar novamente a despesa já representada pelas compras do cartão.

## Dashboard

O dashboard usa o mesmo resumo central do histórico unificado. Ele combina receitas e despesas manuais com transações bancárias de contas vinculadas, depois aplica conciliação e neutralidade de transferências. O saldo consolidado continua usando o saldo do provider para contas vinculadas e o cálculo manual para as demais.

## API e interface

Além das operações de vínculo, foram adicionadas operações protegidas por sessão e CSRF para confirmar ou rejeitar uma possível correspondência bancária. A página Transações mostra a origem de cada lançamento e oferece essas ações somente nos candidatos pertencentes ao usuário autenticado.

## Migrations

- `f4a7c2d9e510`: unicidade do vínculo entre conta externa e conta Nivra;
- `8d2f6a4c1b70`: unicidade da conciliação entre transação bancária e transação manual.

A migration final deve ser aplicada no Neon antes do deploy do código desta etapa:

```powershell
alembic upgrade head
alembic current
```

O resultado esperado é `8d2f6a4c1b70 (head)`.

## Validação

Foram cobertos:

- histórico bancário vinculado e categoria padrão renomeada sem perda da chave;
- fallback para `Outros`;
- sugestão, confirmação e rejeição de conciliação;
- ausência de dupla contagem após confirmação;
- persistência das decisões após re-sync;
- isolamento entre usuários e proteção CSRF;
- transferências bancárias internas neutras;
- pagamento de cartão neutro;
- vínculo, saldo, sincronização e idempotência já existentes.

Resultados finais:

- compilação dos módulos Python: aprovada;
- suíte Python completa: 83 testes aprovados;
- frontend React/TypeScript: build de produção aprovado;
- migrations aplicadas do zero em banco descartável até `8d2f6a4c1b70`;
- `alembic current`: `8d2f6a4c1b70 (head)` no banco descartável;
- `alembic check`: nenhuma operação de upgrade pendente;
- verificação de diferenças do Git: nenhum erro de whitespace.

## Limitações conhecidas

- cartões externos ainda não entram no histórico financeiro principal;
- a conciliação atual atende somente pares simples e não ambíguos;
- revisão em lote, regras configuráveis e casos de múltiplos lançamentos permanecem na Etapa 2H;
- atualização automática depende da futura Etapa 2E — Webhooks;
- a migration `8d2f6a4c1b70` e o deploy ainda precisam ser ativados no Neon/Vercel.

## Próxima tarefa recomendada

**Etapa 2E — Webhooks.**

A próxima etapa deve receber eventos autenticados do provider, manter idempotência e implementar retry e logs estruturados. Ela não faz parte desta entrega.
