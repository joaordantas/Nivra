# Relatório — Gate de UX Mobile da P3.2

Data da validação: 20 de setembro de 2026.

## Escopo

Esta atualização revisou a experiência mobile entregue na **P3.2 — UX e integração de parcelamentos** antes do início da P3.3. Nenhuma regra financeira, migration, tabela ou API foi alterada.

## Problemas encontrados

1. Parcelamentos eram exibidos no final da página extensa de Transações e não tinham acesso direto na navegação.
2. Abrir o histórico focava automaticamente o campo de valor, deslocando o usuário para o formulário mesmo quando ele queria consultar movimentações.
3. O menu inferior escondia Contas e Parcelamentos em uma navegação pouco clara para o uso diário.
4. O modal de um parcelamento longo precisava de comportamento específico para telas pequenas, safe areas e retorno explícito.
5. O estado vazio da nova página de Parcelamentos ainda apontava para uma âncora local inexistente.

## Correções implementadas

- criada a rota protegida `/installments`, com lista, detalhe, edição e acesso à criação;
- adicionado acesso direto a Parcelamentos na sidebar desktop e no menu mobile "Mais";
- reorganizada a navegação inferior mobile para `Início`, `Histórico`, `+`, `Contas` e `Mais`;
- mantidos Cartões, Orçamentos, Metas, Lumi, Configurações, Categorias e logout acessíveis no menu "Mais";
- o foco automático no valor agora ocorre somente quando o formulário é aberto pelo atalho de nova movimentação;
- modais passam a ocupar a tela inteira até 700 px, respeitando safe areas e mantendo o cabeçalho com a ação `Voltar`;
- ampliadas as áreas de toque de ações de transações e identificadores de parcelas;
- bloqueada a rolagem do conteúdo atrás do modal e do menu "Mais";
- corrigido o atalho do estado vazio para abrir o formulário real de criação.

## Matriz de acesso mobile

| Capacidade | Acesso |
| --- | --- |
| Dashboard | `Início` na barra inferior |
| Histórico, busca e filtros | `Histórico` na barra inferior |
| Nova movimentação/parcelamento | botão central `+` |
| Contas | `Contas` na barra inferior |
| Parcelamentos | `Mais > Parcelamentos` |
| Cartões, orçamentos, metas e Lumi | menu `Mais` |
| Configurações e categorias | menu `Mais` |
| Usuário e logout | seção Conta do menu `Mais` |

## Validação visual e funcional

Foram verificados os tamanhos 375 × 812, 390 × 844, 430 × 932, 612 × 900 e 1440 × 900.

Resultados:

- nenhum overflow horizontal relevante;
- barra inferior visível até 612 px e sidebar desktop ativa em 1440 px;
- rota `/installments` preservada após atualização da página;
- detalhe do parcelamento em tela inteira no mobile e centralizado no desktop;
- edição exibe descrição, categoria, conta, salvar e cancelar sem ações encobertas;
- fechamento por `Esc` e por `Voltar` funcionando;
- confirmação explícita permanece antes da exclusão do grupo;
- atalho de criação abre `/transactions?new=1#new-transaction` e foca o valor;
- Histórico abre sem focar o formulário;
- tema escuro preservado durante navegação e atualização;
- logout mobile, novo login e restauração da sessão após F5 validados;
- console do navegador sem erros ou avisos durante a validação final.

A criação e a exclusão persistente de parcelamentos permanecem cobertas pelos testes automatizados da P3.1/P3.2. A auditoria visual não repetiu uma confirmação destrutiva contra dados fora do banco local descartável.

## Verificações técnicas

- suíte Python completa: **118 testes aprovados, 0 falhas**;
- build React/TypeScript: **aprovado**, com 1.929 módulos transformados;
- compilação Python: **aprovada**;
- `git diff --check`: **aprovado**;
- lint: o frontend não possui script de lint configurado; nenhum comando inexistente foi simulado como validação.

## Arquivos alterados

- `frontend/src/app/router.tsx`;
- `frontend/src/components/finance/InstallmentPlans.tsx`;
- `frontend/src/components/finance/MovementForm.tsx`;
- `frontend/src/components/layout/MobileNavigation.tsx`;
- `frontend/src/components/layout/navigation.ts`;
- `frontend/src/components/ui/Modal.tsx`;
- `frontend/src/pages/TransactionsPage.tsx`;
- `frontend/src/pages/InstallmentsPage.tsx`;
- `frontend/src/styles.css`;
- `docs/roadmap.md`;
- `CHANGELOG.md`.

## Limites preservados

- não houve integração com cartões e faturas;
- não houve alteração de valor, quantidade ou data inicial de parcelamentos existentes;
- recorrências continuam pendentes;
- nenhum endpoint ou schema do banco foi modificado.

## Resultado

**MOBILE UX GATE — APROVADO.**

A P3.2 permanece concluída e agora possui acesso consistente no desktop, tablet e celular.

## Próxima tarefa recomendada

**P3.3 — Integração de parcelamentos com cartões e faturas.**

Essa etapa deve distribuir compras parceladas entre ciclos de fatura, comprometer corretamente o limite e projetar faturas futuras sem duplicar a despesa. Ela não foi iniciada neste trabalho.
